import cv2
import matplotlib.pyplot as plt

# 读取两张图片
region = cv2.imread('../in.png')
templates = cv2.imread('../templates/restart.png')

# 将 BGR 转换为 RGB
region = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
templates = cv2.cvtColor(templates, cv2.COLOR_BGR2RGB)

# 显示图片
plt.subplot(1, 2, 1)
plt.imshow(region)
plt.title('region')
plt.axis('off')

plt.subplot(1, 2, 2)
plt.imshow(templates)
plt.title('templates')
plt.axis('off')

plt.show()


import numpy as np

# def mse(imageA, imageB):
#     # 确保两张图片尺寸一致
#     if imageA.shape != imageB.shape:
#         # 将第二张图片调整为第一张图片的尺寸
#         imageB = cv2.resize(imageB, (imageA.shape[1], imageA.shape[0]))
#     # 计算均方误差
#     err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
#     err /= float(imageA.shape[0] * imageA.shape[1])
#     return err
#
# # 计算 MSE
# error = mse(region, templates)
# print(f"MSE: {error}")

print("region尺寸",region.shape)
print("templates尺寸",templates.shape)
# 使用更合适的模板匹配方法
result = cv2.matchTemplate(region, templates, cv2.TM_CCOEFF_NORMED)
max_corr = result.max()
print(f"Template Matching Correlation: {max_corr}")

# 找到匹配位置
min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
print(f"Best match value: {max_val}")