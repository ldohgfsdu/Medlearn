import os

data_dir = 'g:/MedLearn/mini-program/src/data'

print('=== 数据文件大小 ===')
for f in os.listdir(data_dir):
    if f.endswith('.ts'):
        size = os.path.getsize(os.path.join(data_dir, f)) / 1024
        print(f'{f}: {size:.2f} KB')
