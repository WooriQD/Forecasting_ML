import xlwings as xw
import pandas as pd
from datetime import date, datetime
import numpy as np
import matplotlib.pyplot as plt
import sklearn.metrics as mt
from sklearn.tree import export_graphviz
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.model_selection import StratifiedShuffleSplit
from sklearn.model_selection import cross_val_score
from sklearn.model_selection import RandomizedSearchCV
import sklearn.externals
import joblib
from sklearn.metrics import confusion_matrix


def get_data(view=True) -> pd.DataFrame:

    # rawdata 파일 열어서 하나의 dataframe으로
    ## 각 데이터들이 한칸 간격으로 엑셀에 있어야 함
    with xw.App(visible=False) as app:
        excel = xw.Book(r'rawdata.xlsx')
        df_total = pd.DataFrame()

        i = 0
        while True:
            # 엑셀 해당셀에 이름 없으면 종료
            if excel.sheets("Analysis").range(1, 3 * i + 2).value == None:
                break

            # 빈 column으로 구분된 각 dataframe 불러오기
            df = excel.sheets("Analysis").range(1, 3 * i + 1).options(pd.DataFrame,
                                                             index=True,
                                                             expand='table',
                                                             header=False).value

            # df column이름, index 이름 설정 및 필요한 부분만 저장
            df.columns = [df.iloc[0, 0]]
            df.index.name = df.index[1]
            df = df.iloc[2:, :]

            # # 중복 될 때 마지막 것만 남기고 제거
            # df = df.loc[~df.index.duplicated(keep='last')]
            #
            # while 문 돌면서 모든 데이터 합치기
            df_total = pd.concat([df_total, df], axis=1)

            i += 1

        excel.close()

    # 전체 df 오름차순 정렬
    df_total.sort_index(ascending=True, inplace=True)

    # 엑셀로 출력 여부
    if view == True:
        xw.view(df_total)

    return df_total


def add_signal(df_total: pd.DataFrame, end_date, barrier:float, view=True):

    end_date = datetime.strptime(end_date, "%Y-%m-%d")
    df_total = df_total.loc[:end_date, :]

    # signal 생성
    df_total['Diff 10Y'] = df_total['10Y'].diff(1)

    df_total['Diff 10Y'] = df_total['Diff 10Y'].shift(-1)

    data_num = len(df_total.index)
    sig_10Y = []

    for i in range(data_num):
        if df_total['Diff 10Y'][i] < -barrier:
            sig_10Y.append("하락")
        elif (df_total['Diff 10Y'][i] >= -barrier) and (df_total['Diff 10Y'][i] <= barrier):
            sig_10Y.append("보합")
        elif df_total['Diff 10Y'][i] > barrier:
            sig_10Y.append("상승")
        else:
            sig_10Y.append("")

    df_total['sig 10Y'] = sig_10Y

    if view == True:
        xw.view(df_total)

    return df_total


if __name__ == "__main__":
    df = get_data(False)
    df = add_signal(df, '2022-08-22', 0.01, True)

    # 0.모델 fitting --> 마지막 데이터는 예측용이니 제거
    df_fitting = df.iloc[:-1, :]

    # 분석에 사용하지 않을 feature는 # 으로 주석처리
    x_features = [
        '한은업황실적BSI(제조업)',
        '한은업황실적BSI(비제조업)',
        # '한은업황실적BSI(건설업)',
        '한은업황전망BSI(제조업)',
        '한은업황전망BSI(비제조업)',
        # '한은업황전망BSI(건설업)',
        '경제심리지수',
        '소비자물가(yoy)',
        '기대인플레이션율',
        'WTI',
        # 'S&P500골드만삭스원자재지수',
        '기준금리',
        '달러원 환율',
        '코스피지수',
        'S&P500',
        '상해종합지수',
        '소비자동향지수',
        '수출증가율',
        '무역수지',
        '뉴스심리지수',
        '선도금리 10Y',
        '선도금리 3Y',
        'Citi ESI(중국)',
        'MOVE 지수',
        # '현재경기판단CSI',
        # '향후경기전망CSI',
        # '금리수준전망CSI',
    ]
    print(x_features)
    # x, y 데이터 지정
    x = df_fitting[x_features]
    print(f'결측치 존재 여부:\n{x.isnull().sum()}')
    x = x.dropna()
    # xw.view(x)
    print(f'NA 제거 후 결측치 존재 여부:\n{x.isnull().sum()}')

    # Y
    y = df_fitting['sig 10Y'][x.index]
    # xw.view(y)

    # 1. 데이터 분할
    test_ratio = 0.3
    x_train, x_test, y_train, y_test = train_test_split(x,
                                                        y,
                                                        test_size=test_ratio,
                                                        stratify=y,
                                                        random_state=42)

    # 2. 최적 하이퍼 파라미터 결정
    rnd_clf = RandomForestClassifier()

    param_dist_rf = {
        'n_estimators': [50, 100, 500],
        'max_leaf_nodes': [20, 30, 40, 50],
        'max_features': [2, 4, 6, 8]
    }

    rnd_search = RandomizedSearchCV(rnd_clf, param_dist_rf, cv=10, random_state=42)
    rnd_search.fit(x_train, y_train)
    print(rnd_search.best_params_)

    n_estimators = rnd_search.best_params_['n_estimators']
    max_leaf_nodes = rnd_search.best_params_['max_leaf_nodes']
    max_features = rnd_search.best_params_['max_features']


    # 3. 학습 및 K-fold cross validation 평가
    rnd_clf = RandomForestClassifier(n_estimators=n_estimators, max_leaf_nodes=max_leaf_nodes,
                                     max_features=max_features, n_jobs=-1,
                                     random_state=42)
    rnd_scores = cross_val_score(rnd_clf, x_train, y_train, scoring="accuracy", cv=20)
    print("\n<10-fold cross-validation>")
    print("accuracy score mean: ", rnd_scores.mean())



    # 4. 최종 모델 학습
    rnd_clf.fit(x_train, y_train)
    print("\n<AI model: machine learning done >")
    print(f'accuracy_score of train data({1-test_ratio} of sample): ', rnd_clf.score(x_train, y_train))



    # 5. test data 확인
    print(f"accuracy_score of test data({test_ratio} of sample): ", rnd_clf.score(x_test, y_test))
    y_test_pred = rnd_clf.predict(x_test)
    print("accuracy_score of test data: ", mt.accuracy_score(y_test, y_test_pred))



    # 6. confusion matrix 확인
    cm1 = confusion_matrix(y_test, y_test_pred, labels=["상승", "보합", "하락"])
    print("\n<Confusion matrix>")
    print("(of test)")
    print("상승", "보합", "하락")
    print(cm1)
    cm2 = confusion_matrix(y, rnd_clf.predict(x), labels=["상승", "보합", "하락"])
    print("(of all)")
    print("상승", "보합", "하락")
    print(cm2)

    # 7. 변수 중요도 체크
    print("\n<Feature importance>")
    for name, score in zip(x.columns, rnd_clf.feature_importances_):
        print(name, ": ", score)