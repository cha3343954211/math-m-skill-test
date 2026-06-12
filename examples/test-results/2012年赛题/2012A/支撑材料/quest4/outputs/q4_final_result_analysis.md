# Q4 最终结果分析

比较葡萄指标、葡萄酒指标、组合指标对可信评分的预测能力。红葡萄酒中葡萄指标线性模型最佳，CV RMSE=2.609，R²=0.553；白葡萄酒中葡萄酒指标随机森林最佳，CV RMSE=2.687，R²=0.255。模型可以辅助评价葡萄酒质量，但小样本与评委主观性使其不宜完全替代人工品评。

type feature_set          model  n_samples  n_features  cv_rmse   cv_mae     cv_r2
 red       grape LinearBaseline         27         122 2.608507 2.106716  0.553473
 red       grape        RidgeCV         27         122 2.627704 2.137757  0.546877
 red    combined LinearBaseline         27         213 2.992563 2.498090  0.412307
 red    combined        RidgeCV         27         213 3.053108 2.556692  0.388287
 red       grape            PLS         27         122 3.421888 2.677439  0.231586
 red        wine   RandomForest         27          91 3.512708 2.769021  0.190256
 red    combined            PLS         27         213 3.567522 2.897078  0.164788
 red        wine        RidgeCV         27          91 3.669341 3.064886  0.116433
 red    combined   RandomForest         27         213 3.714086 3.054556  0.094752
 red        wine LinearBaseline         27          91 3.903230 3.124754  0.000203
 red       grape   RandomForest         27         122 3.925728 3.366822 -0.011355
 red        wine            PLS         27          91 6.347563 4.226267 -1.644098
