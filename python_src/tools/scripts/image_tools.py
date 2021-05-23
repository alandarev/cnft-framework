from pathlib import Path
from PIL import Image

def load_layer(file_path):
    return Image.open(Path(file_path))

def merge_layers(bg_layer, fg_layer):
    return bg_layer.alpha_composite(fg_layer, (0,0))

def save_layer(file_path, layer):
    layer.save(Path(file_path))
