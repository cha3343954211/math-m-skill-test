# Q2 候选方法与PoC

## M0 Baseline：趋势+年周期Poisson回归 [BASELINE]
- 可行性数字：测试MAE=15.513，AIC=13134.0。

## M1 主模型：分布滞后气象Poisson回归 [CHOSEN]
- 变量：日平均气温、气压、相对湿度及1/3/7日滞后均值，控制长期趋势与年度周期。
- 可行性数字：测试MAE=16.412，AIC=12682.8，较baseline AIC降低451.3；测试MAE变化5.8%。
- 验证：AIC、测试集MAE/RMSE、残差图、关键气象变量RR敏感性。

## M2 普通线性回归 [BACKUP]
- 计数数据非负且方差随均值变化，解释性不如Poisson计数模型，作为备选未采用。
