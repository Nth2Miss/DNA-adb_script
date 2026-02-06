import cv2
import numpy as np
import matplotlib.pyplot as plt

# 读取灰度图像
img = cv2.imread('../templates/restart.png', cv2.IMREAD_GRAYSCALE)

# 创建子图
fig, axes = plt.subplots(3, 4, figsize=(15, 10))

# 原始图像
axes[0, 0].imshow(img, cmap='gray')
axes[0, 0].set_title('Original')
axes[0, 0].axis('off')

# 不同blockSize的效果
block_sizes = [3, 11, 21]
for i, block_size in enumerate(block_sizes):
    binary = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, block_size, 2)
    axes[0, i+1].imshow(binary, cmap='gray')
    axes[0, i+1].set_title(f'blockSize={block_size}')
    axes[0, i+1].axis('off')

# 不同C值的效果
C_values = [-5, 0, 5, 10]
for i, C in enumerate(C_values):
    binary = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY, 11, C)
    axes[1, i].imshow(binary, cmap='gray')
    axes[1, i].set_title(f'C={C}')
    axes[1, i].axis('off')

# 不同方法的对比
# 方法1：均值法
binary_mean = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
axes[2, 0].imshow(binary_mean, cmap='gray')
axes[2, 0].set_title('MEAN_C Method')
axes[2, 0].axis('off')

# 方法2：高斯法
binary_gaussian = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY, 11, 2)
axes[2, 1].imshow(binary_gaussian, cmap='gray')
axes[2, 1].set_title('GAUSSIAN_C Method')
axes[2, 1].axis('off')

# 反向阈值
binary_inv = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, 11, 2)
axes[2, 2].imshow(binary_inv, cmap='gray')
axes[2, 2].set_title('BINARY_INV')
axes[2, 2].axis('off')

# 固定阈值对比
_, binary_fixed = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
axes[2, 3].imshow(binary_fixed, cmap='gray')
axes[2, 3].set_title('Fixed Threshold')
axes[2, 3].axis('off')

plt.tight_layout()
plt.show()