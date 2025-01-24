import os
import aiohttp
import asyncio
import imghdr
import random
import time
import traceback
from PIL import Image
from PIL.PngImagePlugin import PngInfo

def sanitize_filename(filename):
    """Removes invalid characters from filenames and assigns a random number if invalid."""
    import re
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename).strip()
    if not sanitized:
        sanitized = f"{random.randint(10000, 99999)}"  # Random 5-digit number if name is invalid
    return sanitized

def encode_metadata(image_path, metadata_dict):
    """Encodes metadata into a PNG file."""
    metadata = PngInfo()
    for key, value in metadata_dict.items():
        metadata.add_text(str(key), str(value))
    with Image.open(image_path) as img:
        img.save(image_path, pnginfo=metadata)

async def get_clothes(session, group_id, amount):
    """Fetches clothing items from a Roblox group with exponential backoff on errors."""
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

    retries = 5
    backoff_time = 5

    while retries > 0:
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
                    print(f"Unexpected response: {response.status}. Retrying in {backoff_time} seconds...")
                    await asyncio.sleep(backoff_time)
                    backoff_time *= 2  # Exponential backoff
                    retries -= 1
        except Exception as e:
            print(f"Error fetching clothes: {e}. Retrying in {backoff_time} seconds...")
            await asyncio.sleep(backoff_time)
            backoff_time *= 2  # Exponential backoff
            retries -= 1

    print("Max retries reached. Returning no results.")
    return []

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
    """Downloads and saves a clothing item image with a unique filename."""
    try:
        clothing_name = sanitize_filename(clothing_data["name"])  # Sanitize clothing name
        if not os.path.exists("clothes"):
            os.makedirs("clothes")

        # Temporary file path saved as PNG
        temp_path = os.path.join("clothes", f"{clothing_name}.tmp.png")

        while True:
            try:
                async with session.get(f"https://assetdelivery.roblox.com/v1/asset?id={asset_id}", ssl=False) as response:
                    if response.status == 200:
                        image_data = await response.read()

                        # Save the raw data to a temporary PNG file
                        with open(temp_path, "wb") as temp_file:
                            temp_file.write(image_data)

                        # Check file type and ensure it's a PNG or JPEG
                        file_type = imghdr.what(temp_path)
                        if file_type == 'png':  # If it's PNG
                            final_path = os.path.join("clothes", f"{clothing_name}.png")
                            extension = '.png'
                        elif file_type in ['jpeg', 'jpg']:  # If it's JPEG
                            final_path = os.path.join("clothes", f"{clothing_name}.jpg")
                            extension = '.jpg'
                        else:  # For unknown extensions, generate a random filename
                            final_path = os.path.join("clothes", f"{random.randint(10000, 99999)}.png")  # Random filename
                            extension = '.png'

                        # Ensure no filename collisions by checking the final path
                        base_name, ext = os.path.splitext(final_path)
                        counter = 1
                        while os.path.exists(final_path):
                            final_path = f"{base_name}_{counter}{ext}"
                            counter += 1

                        # Rename the temporary file to the final name
                        os.rename(temp_path, final_path)

                        # If the filename was mistakenly saved with ..png_*, we fix it
                        if '..' in final_path or '_0' in final_path:
                            fixed_path = os.path.join("clothes", f"{random.randint(10000, 99999)}.png")
                            os.rename(final_path, fixed_path)
                            final_path = fixed_path

                        # Apply metadata and process the image if it's PNG
                        if extension == '.png':
                            encode_metadata(final_path, clothing_data)

                        print(f"Saved {clothing_name} as {final_path}")
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

def rename_non_png_files():
    """Renames non-PNG files to random numbers with a .png extension."""
    for filename in os.listdir("clothes"):
        file_path = os.path.join("clothes", filename)
        if os.path.isfile(file_path):
            # Check if the file is not a PNG
            if not filename.endswith(".png"):
                new_filename = f"{random.randint(10000, 99999)}.png"
                new_file_path = os.path.join("clothes", new_filename)
                os.rename(file_path, new_file_path)
                print(f"Renamed {filename} to {new_filename}")

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

                # After downloading, rename non-PNG files
                rename_non_png_files()
            else:
                print("No clothing items found.")
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
