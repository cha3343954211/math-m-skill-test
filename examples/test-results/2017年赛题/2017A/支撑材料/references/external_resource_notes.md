# 外部资料与知识库检索记录

## IMA 知识库
- 检索词：`2017A CT系统参数标定 成像`，结果：知识库接口返回空列表。
- 检索词：`CT 成像 Radon 反投影`，结果：知识库接口返回空列表。
- 处理：未直接找到同题资料，因此转为参考公开文档与通用 CT/Radon 反变换理论，所有数值结果均由本项目代码重新计算。

## 外部公开资料
1. scikit-image Radon transform example
   - URL: https://scikit-image.org/docs/stable/auto_examples/transform/plot_radon_transform.html
   - 用途：确认二维图像 Radon 变换、sinogram 与滤波反投影 FBP 的标准实现方式。
   - 转化为本题动作：使用 `skimage.transform.radon` 生成标定模板理论投影，用 `iradon` 进行未知介质重建，并以模板回代重建误差作为验证。
   - 风险：库函数默认坐标约定与题目物理坐标可能不同，因此论文中明确坐标换算并使用模板轮廓匹配修正角度和尺度。

2. CT/Radon 经典理论
   - 关键词：Radon transform; filtered back projection; CT image reconstruction.
   - 用途：建立线积分投影模型 $p_\theta(s)=\int f(x,y)\,dl$ 与反投影重建模型。
   - 转化为本题动作：以已知模板吸收率矩阵为先验，标定角度、探测器间距和旋转中心；对附件3、附件5分别输出 256×256 吸收率矩阵。

## 候选方法与取舍
- Baseline：假设旋转中心为图像中心、180个角度等间隔，直接 FBP 重建。
- 主模型：模板 Radon 投影轮廓匹配标定参数 + FBP 重建 + 阈值组件分割 + 参数扰动灵敏度分析。
- 未采用：迭代代数重建 ART/SART。原因是本题要求全过程交付且要稳定输出，FBP 更可解释、速度快；迭代法可作为后续改进方向。
