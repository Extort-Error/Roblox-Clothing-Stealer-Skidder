from PIL import Image
import os

template_path = "template.png"
clothes_folder = "clothes"
output_folder = "skidded"

if not os.path.exists(output_folder):
    os.makedirs(output_folder)

template = Image.open(template_path)

for filename in os.listdir(clothes_folder):
    if filename.endswith(('.png', '.jpg', '.jpeg')):  # Check for image files
        image_path = os.path.join(clothes_folder, filename)
        
        image = Image.open(image_path)
        
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
        
        image.paste(template, (0, 0), template)  # (0, 0) is the position to overlay
        
        output_path = os.path.join(output_folder, f"modified_{filename}")
        image.save(output_path)

print("Images have been processed and saved in the 'skidded' folder.")
