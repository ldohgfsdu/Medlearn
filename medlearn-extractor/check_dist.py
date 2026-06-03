import os

dist_dir = 'g:/MedLearn/mini-program/dist'

print('=== dist目录文件 ===')
for f in os.listdir(dist_dir):
    if f.endswith('.js'):
        size = os.path.getsize(os.path.join(dist_dir, f)) / 1024
        print(f'{f}: {size:.2f} KB')
