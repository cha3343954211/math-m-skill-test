#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2014C 生猪养殖场经营管理 - 完整数学建模求解
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os
import json

class FarmParams:
    def __init__(self):
        self.max_capacity = 10000
        self.feed_cost_breeder = 8.0
        self.feed_cost_meat = 6.0
        self.feed_cost_piglet = 4.0
        self.meat_price = 14.0
        self.gestation = 114
        self.lactation = 30
        self.grow_to_market = 210
        self.pregnancies_per_year = 2
        self.piglets_per_litter = 9
        self.survival_rate = 0.95
        self.breeder_lifespan = 4
        self.meat_weight = 90
        self.sow_ratio = 2/3

params = FarmParams()

def break_even_analysis(params):
    print("=" * 60)
    print("问题一：盈亏平衡分析")
    print("=" * 60)
    
    def annual_profit_per_sow(N):
        if N <= 0:
            return -np.inf
        p = 1.0 / (params.breeder_lifespan * N)
        p = min(p, 0.99)
        meat_per_sow = N * (1 - p)
        revenue = meat_per_sow * params.meat_weight * params.meat_price
        breeder_cost = 365 * params.feed_cost_breeder
        piglet_cost = N * params.lactation * params.feed_cost_piglet
        return revenue - breeder_cost - piglet_cost
    
    N_min, N_max = 1.0, 100.0
    profit_min = annual_profit_per_sow(N_min)
    profit_max = annual_profit_per_sow(N_max)
    
    if profit_min > 0:
        N_break_even = N_min
    elif profit_max < 0:
        N_break_even = N_max
    else:
        for _ in range(100):
            N_mid = (N_min + N_max) / 2
            if annual_profit_per_sow(N_mid) > 0:
                N_max = N_mid
            else:
                N_min = N_mid
        N_break_even = (N_min + N_max) / 2
    
    p_break = 1.0 / (params.breeder_lifespan * N_break_even)
    p_break = min(p_break, 0.99)
    final_profit = annual_profit_per_sow(N_break_even)
    
    print(f"每头母猪年产仔数 N = {N_break_even:.2f} 头")
    print(f"每胎产仔 = {N_break_even / params.pregnancies_per_year:.2f} 头")
    print(f"稳态下种猪比例 p = {p_break:.4f}")
    print(f"每头母猪年利润 = {final_profit:.2f} 元")
    
    N_range = np.linspace(1, 30, 200)
    profits = [annual_profit_per_sow(N) for N in N_range]
    
    plt.figure(figsize=(10, 6))
    plt.plot(N_range, profits, 'b-', linewidth=2, label='每头母猪年利润（元）')
    plt.axhline(y=0, color='r', linestyle='--', label='盈亏平衡线')
    plt.axvline(x=N_break_even, color='g', linestyle='--', label=f'盈亏平衡点 N={N_break_even:.1f}')
    plt.xlabel('每头母猪年产仔数（头）')
    plt.ylabel('每头母猪年利润（元）')
    plt.title('盈亏平衡分析：年产仔数 vs 每头母猪年利润')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    os.makedirs("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/figures", exist_ok=True)
    plt.savefig("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/figures/问题一_盈亏平衡分析.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    return {
        'break_even_N': round(N_break_even, 2),
        'piglets_per_litter': round(N_break_even / params.pregnancies_per_year, 2),
        'breeder_proportion': round(p_break, 4),
        'annual_profit_at_break_even': round(final_profit, 2)
    }

def saturation_analysis(params, target_capacity=10000):
    print("\n" + "=" * 60)
    print("问题二：饱和规模分析")
    print("=" * 60)
    
    N = params.pregnancies_per_year * params.piglets_per_litter
    p = 1.0 / (params.breeder_lifespan * N * params.survival_rate)
    p = min(p, 0.99)
    print(f"稳态种猪比例 p = {p:.6f}")
    
    coeff = 1.0 / params.sow_ratio + N * (1 - p) * params.survival_rate * (params.grow_to_market / 365)
    S = target_capacity / coeff
    
    total_breeder = S / params.sow_ratio
    annual_meat_出栏 = S * N * (1 - p) * params.survival_rate
    meat_avg_inventory = annual_meat_出栏 * (params.grow_to_market / 365)
    
    print(f"母猪存栏数 S = {S:.0f} 头")
    print(f"总种猪存栏 = {total_breeder:.0f} 头")
    print(f"肉猪平均存栏 = {meat_avg_inventory:.0f} 头")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].bar(['母猪', '公猪', '肉猪（平均）'], [S, S/params.sow_ratio - S, meat_avg_inventory],
                color=['#ff6b6b', '#4ecdc4', '#45b7d1'])
    axes[0].set_title('饱和时存栏结构')
    axes[0].set_ylabel('头数')
    axes[0].grid(True, alpha=0.3)
    
    labels = ['母猪', '公猪', '肉猪']
    sizes = [S, S/params.sow_ratio - S, meat_avg_inventory]
    colors = ['#ff6b6b', '#4ecdc4', '#45b7d1']
    axes[1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
    axes[1].set_title('存栏比例分布')
    
    plt.tight_layout()
    os.makedirs("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest2/figures", exist_ok=True)
    plt.savefig("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest2/figures/问题二_饱和存栏结构.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    return {
        'sow_inventory': round(S, 0),
        'total_breeder': round(total_breeder, 0),
        'meat_inventory': round(meat_avg_inventory, 0),
        'annual_meat_sales': round(annual_meat_出栏, 0),
        'breeder_proportion': round(p, 6),
        'total_capacity': round(total_breeder + meat_avg_inventory, 0)
    }

def optimal_strategy_analysis(params, price_data):
    print("\n" + "=" * 60)
    print("问题三：基于价格预测的最优经营策略")
    print("=" * 60)
    
    days = np.array([p[0] for p in price_data])
    prices = np.array([p[1] for p in price_data])
    print(f"价格预测数据点：{len(days)}个，价格范围：{prices.min():.2f} - {prices.max():.2f} 元/公斤")
    
    from scipy import interpolate
    price_func = interpolate.interp1d(days, prices, kind='linear', fill_value='extrapolate')
    
    p_range = np.linspace(0.005, 0.2, 50)
    profits = []
    
    N = params.pregnancies_per_year * params.piglets_per_litter
    avg_price = np.mean(prices)
    
    for p in p_range:
        S_opt = 1000
        meat_per_sow = N * (1 - p) * params.survival_rate
        revenue_per_sow = meat_per_sow * params.meat_weight * avg_price
        breeder_cost = 365 * params.feed_cost_breeder
        piglet_cost = N * params.lactation * params.feed_cost_piglet
        annual_profit_per_sow = revenue_per_sow - breeder_cost - piglet_cost
        total_profit = annual_profit_per_sow * S_opt
        profits.append(total_profit)
    
    profits = np.array(profits)
    optimal_idx = np.argmax(profits)
    p_optimal = p_range[optimal_idx]
    optimal_profit = profits[optimal_idx]
    
    print(f"最优种猪比例 p = {p_optimal:.4f}")
    print(f"三年总利润 ≈ {optimal_profit/1e6:.2f} 百万元（基准1000头母猪）")
    
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    axes[0].plot(days, prices, 'b-', linewidth=1.5)
    axes[0].axhline(y=np.mean(prices), color='r', linestyle='--', label=f'平均价格 = {np.mean(prices):.2f}元/kg')
    axes[0].set_xlabel('天数')
    axes[0].set_ylabel('价格（元/公斤）')
    axes[0].set_title('三年生猪价格预测曲线')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    axes[1].plot(p_range * 100, profits / 1e6, 'g-', linewidth=2)
    axes[1].axvline(x=p_optimal * 100, color='r', linestyle='--', label=f'最优 p = {p_optimal*100:.2f}%')
    axes[1].set_xlabel('种猪比例 p (%)')
    axes[1].set_ylabel('三年总利润（百万元）')
    axes[1].set_title('种猪比例 vs 三年总利润')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    os.makedirs("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest3/figures", exist_ok=True)
    plt.savefig("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest3/figures/问题三_价格预测与利润分析.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    avg_annual_profit = optimal_profit / 3
    return {
        'optimal_p': round(p_optimal, 4),
        'three_year_profit': round(optimal_profit, 2),
        'avg_annual_profit': round(avg_annual_profit, 2),
        'avg_price': round(np.mean(prices), 2),
        'sow_inventory': 1000,
        'price_range': [round(float(prices.min()), 2), round(float(prices.max()), 2)]
    }

def main():
    print("开始2014C生猪养殖场经营管理的数学建模求解")
    
    price_data = [
        (2, 19.4), (3, 19.6), (4, 19.4), (5, 19.0), (6, 19.1), (7, 19.2), (8, 19.3), (9, 19.4), (10, 19.5),
        (11, 19.3), (12, 18.9), (13, 18.3), (14, 17.8), (15, 17.0), (16, 17.0), (17, 16.7), (18, 16.6), (19, 17.1),
        (20, 17.2), (21, 17.3), (22, 17.5), (23, 17.4), (24, 17.0), (25, 16.7), (26, 16.1), (27, 15.8), (28, 15.6),
        (29, 15.1), (30, 14.3), (31, 14.2), (32, 14.3), (33, 14.1), (34, 13.7), (35, 13.6), (36, 13.5), (37, 14.0),
        (38, 13.6), (39, 13.7), (40, 13.7), (41, 13.7), (42, 13.8), (43, 14.1), (44, 14.2), (45, 14.5), (46, 14.8),
        (47, 14.6), (48, 14.6), (49, 14.5), (50, 14.4), (51, 14.4), (52, 14.7), (53, 15.0), (54, 15.9), (55, 16.2),
        (56, 16.4), (57, 17.1), (58, 17.5), (59, 17.0), (60, 15.8), (61, 15.6), (62, 14.3), (63, 13.8), (64, 13.6),
        (65, 13.1), (66, 12.4), (67, 12.3), (68, 12.3), (69, 12.1), (70, 12.6), (71, 13.7), (72, 14.4), (73, 14.2),
        (74, 14.3), (75, 14.3), (76, 14.7), (77, 15.0), (78, 15.6), (79, 15.8), (80, 15.7), (81, 16.0), (82, 15.8),
        (83, 15.5), (84, 15.6), (85, 15.5), (86, 15.5), (87, 15.5), (88, 15.6), (89, 15.8), (90, 15.9), (91, 15.6),
        (92, 15.4), (93, 14.6), (94, 13.6), (95, 13.0), (96, 12.8), (97, 12.6), (98, 12.1), (99, 11.8), (100, 11.4),
        (101, 10.9), (102, 10.8), (103, 10.7), (104, 10.8), (105, 11.9), (106, 13.8), (107, 13.7), (108, 13.3),
        (109, 13.1), (110, 13.4)
    ]
    
    results1 = break_even_analysis(params)
    os.makedirs("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/outputs", exist_ok=True)
    with open("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/outputs/results.json", 'w', encoding='utf-8') as f:
        json.dump(results1, f, indent=2, ensure_ascii=False)
    
    results2 = saturation_analysis(params, params.max_capacity)
    with open("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest2/outputs/results.json", 'w', encoding='utf-8') as f:
        json.dump(results2, f, indent=2, ensure_ascii=False)
    
    results3 = optimal_strategy_analysis(params, price_data)
    with open("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest3/outputs/results.json", 'w', encoding='utf-8') as f:
        json.dump(results3, f, indent=2, ensure_ascii=False)
    
    all_results = {
        'problem1': results1,
        'problem2': results2,
        'problem3': results3,
        'parameters': {
            'max_capacity': params.max_capacity,
            'meat_weight': params.meat_weight,
            'breeder_lifespan': params.breeder_lifespan,
            'piglets_per_litter': params.piglets_per_litter,
            'pregnancies_per_year': params.pregnancies_per_year
        }
    }
    with open("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/outputs/final_results.json", 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print("\n所有问题求解完成！")
    print(f"问题一：每头母猪年产仔 {results1['break_even_N']:.1f} 头可盈亏平衡")
    print(f"问题二：饱和时母猪存栏 {results2['sow_inventory']:.0f} 头，种猪比例 {results2['breeder_proportion']:.4f}")
    print(f"问题三：最优种猪比例 {results3['optimal_p']*100:.2f}%，平均年利润 {results3['avg_annual_profit']/1e6:.2f} 百万元")

if __name__ == "__main__":
    main()
