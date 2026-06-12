#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2014C 问题一：盈亏平衡分析
计算达到盈亏平衡点时，每头母猪每年平均产仔量需要达到多少
"""

import numpy as np
import matplotlib.pyplot as plt
import os

# ============================================================
# 参数定义
# ============================================================
# 根据2014年国赛C题背景和实际养殖数据，收集相关参数
# 以下为合理假设值（需根据实际数据调整）

# 成本参数（元/头/天）
FEED_COST_BREEDER = 8.0   # 种猪饲料成本（母猪/公猪）
FEED_COST_MEAT = 6.0      # 肉猪饲料成本
FEED_COST_PIGLET = 4.0    # 乳猪/小猪饲料成本

# 价格参数（元/公斤，盈亏平衡时不考虑利润）
MEAT_PRICE = 14.0         # 肉猪出栏价格
BREEDER_PRICE = 0         # 种猪内部循环，不计收入

# 生长周期参数（天）
GESTATION = 114           # 母猪怀孕期
LACTATION = 30            # 哺乳期
GROW_TO_MARKET = 210      # 小猪长成肉猪出栏所需时间（约7个月）
TOTAL_CYCLE = GESTATION + LACTATION + GROW_TO_MARKET  # 约354天 ≈ 11.8个月

# 繁殖参数
PREGNANCIES_PER_YEAR = 2  # 生育期母猪年产2胎
PIGLETS_PER_LITTER = 9    # 每胎成活9头
SURVIVAL_RATE = 0.95      # 小猪存活率（95%）

# 养殖场参数
MAX_CAPACITY = 10000      # 最大养殖规模（头）

# 种猪寿命（年）
BREEDER_LIFESPAN = 4      # 种猪平均生育期4年

# ============================================================
# 问题一：盈亏平衡分析
# ============================================================
def break_even_analysis():
    """
    计算达到盈亏平衡点时，每头母猪每年平均产仔量需要达到多少
    
    盈亏平衡条件：总收入 = 总成本
    
    在稳态下，我们考虑一个完整的繁殖周期内的收支平衡
    
    设每头母猪每年产仔数为 N（待求），则：
    - 每年每头母猪产生的肉猪数量 = N * (1 - p) （p为选作种猪的比例）
    - 但实际上，稳态下需要考虑种猪的更替
    
    简化模型：在稳态下，种猪数量恒定，肉猪出栏量稳定
    """
    
    print("=" * 60)
    print("问题一：盈亏平衡分析")
    print("=" * 60)
    
    # 关键假设：
    # 1. 不考虑种猪的销售收入（种猪内部循环）
    # 2. 所有存活的小猪中，比例为 p 成为种猪，(1-p) 成为肉猪
    # 3. 稳态下，种猪数量恒定（新种猪补充淘汰的种猪）
    
    # 设母猪数量为 S，每年每头母猪产仔数为 N
    # 每年新生小猪数 = S * N * PREGNANCIES_PER_YEAR * PIGLETS_PER_LITTER * SURVIVAL_RATE
    
    # 但题目简化为：每胎成活9头，年产2胎，所以每头母猪每年产仔 = 18头
    # 问题求：这个产仔数需要达到多少才能盈亏平衡
    
    # 简化模型：考虑一个母猪的生命周期
    
    # 一头母猪的总成本（4年生育期内）：
    # 饲料成本：每天 * 365天 * 4年 = 365 * 4 * FEED_COST_BREEDER
    # 但实际只考虑生育期，约3-5年，取4年
    
    # 一头母猪在4年内产生的肉猪：
    # 每年产仔数 = N * 2胎 * 9头 = 18N
    # 其中比例 p 成为种猪（内部循环），(1-p) 成为肉猪
    # 4年内肉猪总量 = 4 * 18N * (1-p) = 72N(1-p)
    
    # 肉猪销售收入：72N(1-p) * 平均体重 * MEAT_PRICE
    # 假设肉猪出栏体重约90kg
    PIG_WEIGHT = 90  # 肉猪出栏平均体重（kg）
    
    # 一头母猪4年内的总成本：
    # 饲料成本：4年 * 365天 * FEED_COST_BREEDER
    # 但种猪从小猪开始养，也需要成本
    # 简化：只考虑种猪成年后的饲料成本
    
    # 更合理的稳态分析：
    # 设稳态下母猪数量为 S
    # 每年需要补充的种猪数 = S / BREEDER_LIFESPAN （每年淘汰1/4）
    # 这些种猪需要从新生小猪中选
    
    # 稳态条件：
    # 每年新生小猪数 = S * N * 2 * 9 = 18SN
    # 其中需要保留的种猪数 = S / BREEDER_LIFESPAN （补充淘汰）
    # 剩下的成为肉猪：18SN - S/BREEDER_LIFESPAN
    
    # 但还要考虑肉猪的饲养成本
    # 肉猪从出生到出栏的总成本 = 小猪成本 + 肉猪生长成本
    # 小猪成本（到断奶）：约30天 * FEED_COST_PIGLET
    # 肉猪生长成本：GROW_TO_MARKET天 * FEED_COST_MEAT
    
    # 总成本 = 种猪饲料成本 + 肉猪饲料成本
    # 总收入 = 肉猪销售收入
    
    # 稳态下的年成本：
    # 种猪饲料成本：S * 365 * FEED_COST_BREEDER
    # 肉猪饲料成本：需要计算肉猪的饲养周期和数量
    
    # 更精确的稳态模型：
    # 设稳态时：母猪数 S，肉猪平均存栏数 R
    
    # 每年肉猪出栏数 = S * N * 2 * 9 * (1 - p)  （假设p为种猪比例）
    # 但稳态下，需要满足：种猪补充数 = S / BREEDER_LIFESPAN = S * p * N * 2 * 9
    # 所以：p = (S / BREEDER_LIFESPAN) / (S * N * 2 * 9) = 1 / (BREEDER_LIFESPAN * N * 18)
    
    # 每年肉猪出栏数 = S * N * 18 * (1 - p)
    
    # 肉猪平均存栏数（根据排队论）：
    # 每个肉猪从出生到出栏需要 TOTAL_CYCLE / 365 年
    # 平均存栏 = 年出栏数 * 饲养周期（年）
    
    # 简化：使用稳态平衡方程
    
    # 目标：求 N 使得年利润 = 0
    
    # 年利润 = 年销售收入 - 年总成本
    # 年销售收入 = 肉猪出栏数 * 体重 * 价格
    # 年总成本 = 种猪饲料成本 + 肉猪饲料成本
    
    # 设 p 为选作种猪的比例（待确定，由稳态决定）
    # p = 1 / (BREEDER_LIFESPAN * N * 18)
    
    # 年肉猪出栏数 = S * N * 18 * (1 - p)
    # 年销售收入 = S * N * 18 * (1 - p) * PIG_WEIGHT * MEAT_PRICE
    
    # 种猪年饲料成本 = S * 365 * FEED_COST_BREEDER
    
    # 肉猪年饲料成本 = 肉猪平均存栏数 * 365 * FEED_COST_MEAT
    # 肉猪平均存栏数 ≈ 年出栏数 * (TOTAL_CYCLE / 365) / 2 （平均存栏为出栏的一半）
    # 更精确：根据Little定律，平均存栏 = 年出栏数 * 平均在园时间
    
    # 为简化，使用：肉猪平均存栏 ≈ 年出栏数 * (GROW_TO_MARKET / 365)
    
    # 现在我们来求解 N
    
    # 定义利润函数
    def profit(N, S=100):
        """计算给定每头母猪年产仔数N时的年利润（以100头母猪为基准）"""
        if N <= 0:
            return -np.inf
        
        # 种猪比例 p
        p = 1.0 / (BREEDER_LIFESPAN * N * 18)
        if p >= 1:  # 比例不能超过1
            p = 0.99
        
        # 年肉猪出栏数
        annual出栏 = S * N * 18 * (1 - p)
        
        # 年销售收入
        revenue = annual出栏 * PIG_WEIGHT * MEAT_PRICE
        
        # 种猪饲料成本
        breeder_cost = S * 365 * FEED_COST_BREEDER
        
        # 肉猪饲料成本（平均存栏估算）
        # 肉猪平均存栏 = annual出栏 * (GROW_TO_MARKET / 365)
        avg_meat_inventory = annual出栏 * (GROW_TO_MARKET / 365)
        meat_cost = avg_meat_inventory * 365 * FEED_COST_MEAT
        
        # 小猪成本（断奶前）
        # 每年新生小猪数 = S * N * 18
        # 断奶前成本 = 新生小猪数 * LACTATION * FEED_COST_PIGLET
        annual_piglets = S * N * 18
        piglet_cost = annual_piglets * LACTATION * FEED_COST_PIGLET
        
        total_cost = breeder_cost + meat_cost + piglet_cost
        
        return revenue - total_cost
    
    # 寻找盈亏平衡点（利润=0）
    # 使用二分法搜索
    N_min, N_max = 1.0, 50.0
    tol = 0.01
    
    # 检查端点
    profit_min = profit(N_min)
    profit_max = profit(N_max)
    
    if profit_min > 0:
        # 即使最小产仔数也盈利，返回最小值
        N_break_even = N_min
        print(f"警告：即使年产仔{N_min}头也盈利，盈亏平衡点低于{N_min}")
    elif profit_max < 0:
        # 即使最大产仔数也亏损，返回最大值
        N_break_even = N_max
        print(f"警告：即使年产仔{N_max}头也亏损，盈亏平衡点高于{N_max}")
    else:
        # 二分法求解
        for _ in range(100):
            N_mid = (N_min + N_max) / 2
            profit_mid = profit(N_mid)
            if abs(profit_mid) < tol:
                N_break_even = N_mid
                break
            if profit_mid > 0:
                N_max = N_mid
            else:
                N_min = N_mid
        else:
            N_break_even = (N_min + N_max) / 2
    
    print(f"\n盈亏平衡分析结果（基于100头母猪的基准）：")
    print(f"  每头母猪年产仔数 N = {N_break_even:.2f} 头")
    print(f"  相当于每胎产仔 = {N_break_even / 2:.2f} 头")
    
    # 计算此时的种猪比例
    p_break = 1.0 / (BREEDER_LIFESPAN * N_break_even * 18)
    print(f"  稳态下种猪比例 p = {p_break:.4f} ({p_break*100:.2f}%)")
    
    # 计算此时的年利润（应该接近0）
    final_profit = profit(N_break_even)
    print(f"  年利润 = {final_profit:.2f} 元")
    
    # 绘制利润曲线
    N_range = np.linspace(1, 30, 100)
    profits = [profit(N) for N in N_range]
    
    plt.figure(figsize=(10, 6))
    plt.plot(N_range, profits, 'b-', linewidth=2, label='年利润')
    plt.axhline(y=0, color='r', linestyle='--', label='盈亏平衡线')
    plt.axvline(x=N_break_even, color='g', linestyle='--', label=f'盈亏平衡点 N={N_break_even:.2f}')
    plt.xlabel('每头母猪年产仔数（头）')
    plt.ylabel('年利润（元，基准100头母猪）')
    plt.title('盈亏平衡分析：年产仔数 vs 年利润')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    os.makedirs("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/figures", exist_ok=True)
    plt.savefig("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/figures/问题一_盈亏平衡分析.png", dpi=300, bbox_inches='tight')
    plt.close()
    
    return {
        'break_even_N': N_break_even,
        'piglets_per_litter': N_break_even / 2,
        'breeder_proportion': p_break,
        'annual_profit_at_break_even': final_profit
    }

# ============================================================
# 运行分析
# ============================================================
if __name__ == "__main__":
    results = break_even_analysis()
    
    # 保存结果
    os.makedirs("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/outputs", exist_ok=True)
    import json
    with open("<LOCAL_MATH_MODELING_TEST_ROOT>/2014年赛题/2014C/支撑材料/quest1/outputs/results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print("\n结果已保存到：quest1/outputs/results.json")