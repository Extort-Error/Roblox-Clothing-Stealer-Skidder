import os
import aiohttp
import asyncio
import traceback
from PIL import Image
from PIL.PngImagePlugin import PngInfo

def sanitize_filename(filename):
    """Removes invalid characters from filenames."""
    import re
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def encode_metadata(image_path, metadata_dict):
    """Encodes metadata into a PNG file."""
    metadata = PngInfo()
    for key, value in metadata_dict.items():
        metadata.add_text(str(key), str(value))
    with Image.open(image_path) as img:
        img.save(image_path, pnginfo=metadata)

def process_image(filepath, template_path="template.png"):
    """Applies a template overlay to the image."""
    try:
        img1 = Image.open(filepath).convert("RGBA")
        img2 = Image.open(template_path).convert("RGBA")
        
        # Use Image.Resampling.LANCZOS instead of ANTIALIAS
        img2 = img2.resize(img1.size, Image.Resampling.LANCZOS)
        
        img1.paste(img2, (0, 0), img2)

        img1.save(filepath)  
        print(f"Processed image saved at {filepath}")
    except Exception as e:
        print(f"Error processing image {filepath}: {e}")

async def get_clothes(session, group_id, amount):
    """Fetches clothing items from a Roblox group."""
    cursor = ''
    assets = []
    url = f"https://catalog.roblox.com/v1/search/items/details"
    params = {
        "Category": "Clothing",
        "CreatorType": "Group",
        "IncludeNotForSale": "false",
        "Limit": 30,
        "CreatorTargetId": group_id,
    }

    while True:
        try:
            async with session.get(url, params={**params, "cursor": cursor}, ssl=False) as response:
                if response.status == 200:
                    data = await response.json()
                    clothings = data.get("data", [])
                    for asset in clothings:
                        assets.append({
                            "name": asset.get("name"),
                            "description": asset.get("description"),
                            "assetType": asset.get("assetType"),
                            "id": asset.get("id")
                        })
                    cursor = data.get("nextPageCursor")
                    if not cursor or len(assets) >= int(amount):
                        return assets
                else:
                    print(f"Unexpected response: {response.status}. Retrying in 5 seconds...")
                    await asyncio.sleep(5)
        except Exception as e:
            print(f"Error fetching clothes: {e}. Retrying in 5 seconds...")
            await asyncio.sleep(5)

async def get_asset_image_url(session, clothing_id):
    """Fetches the image URL for a clothing item."""
    try:
        url = f"https://assetdelivery.roblox.com/v1/asset?id={clothing_id}"
        async with session.get(url, ssl=False) as response:
            if response.status == 200:
                content = await response.text()
                return content.split('<url>http://www.roblox.com/asset/?id=')[1].split('</url>')[0]
            else:
                print(f"Failed to fetch asset {clothing_id}: {response.status}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
                return None
    except Exception as e:
        print(f"Error fetching asset image URL for {clothing_id}: {e}. Retrying in 5 seconds...")
        await asyncio.sleep(5)
        return None

async def download_and_save(session, asset_id, clothing_data):
    """Downloads and saves a clothing item image."""
    try:
        clothing_name = sanitize_filename(clothing_data["name"])
        save_path = os.path.join("clothes", f"{clothing_name}.png")
        if not os.path.exists("clothes"):
            os.makedirs("clothes")

        if os.path.exists(save_path):
            print(f"File {clothing_name}.png already exists. Skipping.")
            return

        while True:
            try:
                async with session.get(f"https://assetdelivery.roblox.com/v1/asset?id={asset_id}") as response:
                    if response.status == 200:
                        image_data = await response.read()
                        with open(save_path, "wb") as file:
                            file.write(image_data)
                        encode_metadata(save_path, clothing_data)
                        process_image(save_path)
                        print(f"Saved and processed {clothing_name} at {save_path}")
                        break
                    else:
                        print(f"Failed to download asset {asset_id}: {response.status}. Retrying in 5 seconds...")
                        await asyncio.sleep(5)
            except Exception as e:
                print(f"Error downloading asset {asset_id}: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
    except Exception as e:
        print(f"Unexpected error: {e}. Retrying in 5 seconds...")
        await asyncio.sleep(5)

async def main():
    try:
        group_id = input("Enter the Roblox group ID: ")
        amount = input("Enter the number of clothing items to scrape: ")

        async with aiohttp.ClientSession() as session:
            print("Fetching clothing items...")
            clothing_items = await get_clothes(session, group_id, amount)
            if clothing_items:
                tasks = []
                for clothing in clothing_items:
                    clothing_id = clothing["id"]
                    image_url = await get_asset_image_url(session, clothing_id)
                    if image_url:
                        tasks.append(download_and_save(session, image_url, clothing))
                await asyncio.gather(*tasks)
            else:
                print("No clothing items found.")
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
