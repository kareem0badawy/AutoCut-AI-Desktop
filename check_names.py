import os
import json

images_folder = "J:/Coding/Desktop/AutoCut/assets/images"
files = os.listdir(images_folder)
for f in files:
    print(repr(f))
