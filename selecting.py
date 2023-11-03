import os
import csv
import argparse
import pandas as pd
import tkinter as tk
from PIL import Image, ImageTk
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import reverse_geocoder as rg
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import shutil

class ImageSorter:
    def __init__(self, args, master, images, coordinates):
        self.master = master
        self.images = images
        self.coordinates = coordinates
        self.source_folder = args.source_folder
        self.select_folder = args.select_folder
        self.index = 0

        master.title("Image Viewer")
        self.frame = tk.Frame(master)
        self.frame.pack()

        self.canvas = tk.Canvas(self.frame)
        self.canvas.pack(side="left")

        self.label = tk.Label(self.frame)
        self.label.pack(side="right")
        
        # Create the figure and canvas only once
        self.fig = plt.Figure(figsize=(5, 3))
        self.ax = self.fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack()

        # Load initial image
        self.load_image()

        # Bind keys
        master.bind("<Right>", self.next_image)
        master.bind("<Left>", self.prev_image)
        master.bind("<space>", self.copy_image)

    def load_image(self):
        image_path = os.path.join(self.source_folder, f"{self.images[self.index]}.jpg")
        pil_image = Image.open(image_path)
        self.tk_image = ImageTk.PhotoImage(pil_image)
        self.label.config(image=self.tk_image)

        # Clear the canvas and create a new map
        self.ax.clear()
        self.ax.set_global()
        self.ax.stock_img()
        self.ax.add_feature(cfeature.COASTLINE)
        self.ax.add_feature(cfeature.BORDERS, linestyle=':')

        # Add the location of the image as a red dot
        lon, lat = self.coordinates[self.index]
        self.ax.plot(lon, lat, 'ro', transform=ccrs.Geodetic())
        
        self.canvas.draw()

    def next_image(self, event):
        # Go to the next image
        self.index = (self.index + 1) % len(self.images)
        self.load_image()

    def prev_image(self, event):
        # Go to the previous image
        self.index = (self.index - 1) % len(self.images)
        self.load_image()

    def copy_image(self, event):
        # Copy the current image to the SELECT_FOLDER
        current_image_path = os.path.join(self.source_folder, f"{self.images[self.index]}.jpg")
        destination_path = os.path.join(self.select_folder, f"{self.images[self.index]}.jpg")
        shutil.copy(current_image_path, destination_path)

def load_images_and_coordinates(csv_file, source_folder):
    # Load the CSV
    df = pd.read_csv(csv_file)
    
    df = df.sample(n=1000)

    # Get the image filenames and their coordinates
    image_ids = df['image_id'].tolist()
    coordinates = df[['longitude', 'latitude']].values.tolist()
    
    

    # Filter out images that don't exist
    valid_images = [img_id for img_id in image_ids if os.path.exists(os.path.join(source_folder, f"{img_id}.jpg"))]
    valid_coordinates = [coordinates[image_ids.index(img_id)] for img_id in valid_images]

    return valid_images, valid_coordinates


def create_select_csv(select_folder, original_csv, output_csv_path):
    # Read the original CSV and create a mapping from image_id to coordinates
    image_to_coords = {}
    with open(original_csv, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            image_to_coords[row['image_id']] = (float(row['latitude']), float(row['longitude']))  # reverse_geocoder expects (lat, lon)

    # List the files in the select_folder
    selected_files = [f for f in os.listdir(select_folder) if os.path.isfile(os.path.join(select_folder, f))]

    # Write the select.csv file
    with open(output_csv_path, 'w', newline='') as csvfile:
        fieldnames = ['image_id', 'longitude', 'latitude', 'city', 'area', 'region', 'country']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for file in selected_files:
            # Extract image_id from filename
            image_id = os.path.splitext(file)[0]
            if image_id in image_to_coords:
                # Perform reverse geocoding
                coordinates = image_to_coords[image_id]
                results = rg.search(coordinates)  # Returns a list of dictionaries
                result = results[0]  # Get the first result

                # Write to CSV if image_id exists in the mapping
                writer.writerow({
                    'image_id': image_id,
                    'longitude': coordinates[1],
                    'latitude': coordinates[0],
                    'city': result['name'],
                    'area': result['admin2'],
                    'region': result['admin1'],
                    'country': result['cc']
                })

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Image Viewer with Map')
    parser.add_argument('--source_folder', type=str, required=False, help='Folder with images', default='/home/ign.fr/llandrieu/Documents/code/geoscrapping/images/test')
    parser.add_argument('--select_folder', type=str, required=False, help='Folder to copy selected images into', default='/home/ign.fr/llandrieu/Documents/code/geoscrapping/images/select')
    parser.add_argument('--csv_file', type=str, required=False, help='CSV file with image ids and coordinates', default='/home/ign.fr/llandrieu/Documents/code/geoscrapping/processed/test.csv')

    args = parser.parse_args()

    # Ensure the select folder exists
    if not os.path.exists(args.select_folder):
        os.makedirs(args.select_folder)
        
    if True:

        images, coordinates = load_images_and_coordinates(args.csv_file, args.source_folder)

        root = tk.Tk()
        app = ImageSorter(args, root, images, coordinates)
        root.mainloop()
    
    else:
        create_select_csv(args.select_folder, args.csv_file, '/home/ign.fr/llandrieu/Documents/code/geoscrapping/processed/select.csv')
    