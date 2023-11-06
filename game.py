"""Requires gradio==3.44.0"""
import io
import os
import uuid
import matplotlib
import time
matplotlib.use('Agg')
from os.path import join
from PIL import Image
import pandas as pd
import reverse_geocoder as rg
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from math import radians, sin, cos, sqrt, asin, exp
from collections import defaultdict

IMAGE_FOLDER = './select'
CSV_FILE = './select.csv'
RESULTS_DIR = './results'
RULES = """# Plonk 🌍 🌎 🌏
## Total time: 50 pictures ~ 5min
### How it works:
- Click on the map 🗺️ (left) to indicate where do you think the image 🖼️ (right) was captured!
- Click next to move to the next image.
⚠️ Your selection is final!
### Click "start" to begin...
"""

def haversine(lat1, lon1, lat2, lon2):
    if (lat1 is None) or (lon1 is None) or (lat2 is None) or (lon2 is None):
        return 0
    R = 6371  # radius of the earth in km
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = (
        sin(dLat / 2.0) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2.0) ** 2
    )
    c = 2 * asin(sqrt(a))
    distance = R * c
    return distance

def geoscore(d):
    return 5000 * exp(-d / 1492.7)


class Engine(object):
    def __init__(self, image_folder, csv_file, cache_path):
        self.image_folder = image_folder
        self.load_images_and_coordinates(csv_file)
        self.cache_path = cache_path
          
        # Initialize the score and distance lists
        self.index = 0
        self.stats = defaultdict(list)

        # Create the figure and canvas only once
        self.fig = plt.Figure(figsize=(10, 6))
        self.ax = self.fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        self.MIN_LON, self.MAX_LON, self.MIN_LAT, self.MAX_LAT = self.ax.get_extent()

    def load_images_and_coordinates(self, csv_file):
        # Load the CSV
        df = pd.read_csv(csv_file)

        # Get the image filenames and their coordinates
        self.images = df['image_id'].tolist()[:]
        self.coordinates = df[['longitude', 'latitude']].values.tolist()[:]
        self.admins = df[['city', 'area', 'region', 'country']].values.tolist()[:]


    def isfinal(self):
        return self.index == len(self.images)-1

    def load_image(self):
        if self.index > len(self.images)-1:          
            self.master.update_idletasks()
            self.finish()

        self.ax.clear()
        self.ax.set_global()
        self.ax.stock_img()
        self.ax.add_feature(cfeature.COASTLINE)
        self.ax.add_feature(cfeature.BORDERS, linestyle=':')
        self.fig.canvas.draw()
        pil = self.get_figure()
        self.set_clock()
        return pil, os.path.join(self.image_folder, f"{self.images[self.index]}.jpg"), '### ' + str(self.index + 1) + '/' + str(len(self.images))

    def get_figure(self):
        img_buf = io.BytesIO()
        self.fig.savefig(img_buf, format='png', bbox_inches='tight', pad_inches=0, dpi=300)
        pil = Image.open(img_buf)
        self.width, self.height = pil.size
        return pil

    def normalize_pixels(self, click_lon, click_lat):
        return self.MIN_LON + click_lon * (self.MAX_LON-self.MIN_LON) / self.width, self.MIN_LAT + (self.height - click_lat+1) * (self.MAX_LAT-self.MIN_LAT) / self.height

    def set_clock(self):
        self.time = time.time()

    def get_clock(self):
        return time.time() - self.time

    def click(self, click_lon, click_lat):
        time_elapsed = self.get_clock()
        self.stats['times'].append(time_elapsed)

        # convert click_lon, click_lat to lat, lon (given that you have the borders of the image)
        # click_lon and click_lat is in pixels
        # lon and lat is in degrees
        click_lon, click_lat = self.normalize_pixels(click_lon, click_lat)
        self.stats['clicked_locations'].append((click_lat, click_lon))
        true_lon, true_lat = self.coordinates[self.index]

        self.ax.plot(click_lon, click_lat, 'bo', transform=ccrs.Geodetic())
        self.ax.plot([true_lon, click_lon], [true_lat, click_lat], color='blue', linewidth=1, transform=ccrs.Geodetic())
        self.ax.plot(true_lon, true_lat, 'rx', transform=ccrs.Geodetic())
              
        distance = haversine(true_lat, true_lon, click_lat, click_lon)
        score = geoscore(distance)
        self.stats['scores'].append(score)
        self.stats['distances'].append(distance)
        
        average_text = self.update_average_display()         
        result_text = (f"### GeoScore: {score:.0f}, distance: {distance:.0f} km\n  ")
       
        self.cache(self.index+1, score, distance, (click_lat, click_lon), time_elapsed)
        return self.get_figure(), result_text + average_text

    def next_image(self):
        # Go to the next image
        self.index += 1
        return self.load_image()
        
    def update_average_display(self):
        # Calculate the average values
        avg_score = sum(self.stats['scores']) / len(self.stats['scores']) if self.stats['scores'] else 0
        avg_distance = sum(self.stats['distances']) / len(self.stats['distances']) if self.stats['distances'] else 0

        # Update the text box
        return f"### Average GeoScore: {avg_score:.0f}, Average distance: {avg_distance:.0f} km"
    
    def finish(self):
        clicks = rg.search(self.stats['clicked_locations'])
        clicked_admins = [[click['name'], click['admin2'], click['admin1'], click['cc']] for click in clicks]
        
        correct = [0,0,0,0]
        valid = [0,0,0,0]
        
        for clicked_admin, true_admin in zip(clicked_admins, self.admins):
            for i in range(4):
                if true_admin[i]!= 'nan':
                    valid[i] += 1
                if true_admin[i] == clicked_admin[i]:
                    correct[i] += 1
                    
        avg_city_accuracy = correct[0] / valid[0]
        avg_area_accuracy = correct[1] / valid[1]
        avg_region_accuracy = correct[2] / valid[2]
        avg_country_accuracy = correct[3] / valid[3]
        
        avg_score = sum(self.stats['scores']) / len(self.stats['scores']) if self.stats['scores'] else 0
        avg_distance = sum(self.stats['distances']) / len(self.stats['distances']) if self.stats['distances'] else 0

        final_results = (
            f"Average GeoScore: {avg_score:.0f}  \n" + 
            f"Average distance: {avg_distance:.0f} km  \n" + 
            f"Country Acc: {100*avg_country_accuracy:.1f}  \n" + 
            f"Region Acc: {100*avg_region_accuracy:.1f}  \n" + 
            f"Area Acc: {100*avg_area_accuracy:.1f}  \n" + 
            f"City Acc: {100*avg_city_accuracy:.1f}"
        )

        self.cache_final(final_results)

        # Update the text box
        return f"# Your stats 🌍\n" + final_results + f"  \n# Thanks for playing ❤️"
        
    # Function to save the game state
    def cache(self, index, score, distance, location, time_elapsed):
        if not os.path.exists(self.cache_path):
            os.makedirs(self.cache_path)

        with open(join(self.cache_path, str(index).zfill(2) + '.txt'), 'w') as f:
            print(f"{score}, {distance}, {location[0]}, {location[1]}, {time_elapsed}", file=f)

    # Function to save the game state
    def cache_final(self, final_results):
        times = ', '.join(map(str, self.stats['times']))
        with open(join(self.cache_path, 'full.txt'), 'w') as f:
            print(f"{final_results}" + '\n Times: ' + times, file=f)



if __name__ == "__main__":
    import gradio as gr
    def click(state, evt: gr.SelectData):
        if state['clicked']:
            return gr.update(), gr.update()
        x, y = evt.index
        state['clicked'] = True
        image, text = state['engine'].click(x, y)
        return gr.update(value=image), gr.update(value=text)

    def next_(state):
        if state['clicked']:
            if state['engine'].isfinal():
                text = state['engine'].finish()
                return gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), gr.update(value=text), gr.update(visible=False)
            else:
                fig, image, text = state['engine'].next_image()
                state['clicked'] = False
                return gr.update(value=fig), gr.update(value=image), gr.update(value=text), gr.update(), gr.update()
        else:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()

    def start(state):
        # create a unique random temporary name under CACHE_DIR
        # generate random hex and make sure it doesn't exist under CACHE_DIR
        while True:
            path = str(uuid.uuid4().hex)
            name = os.path.join(RESULTS_DIR, path)
            if not os.path.exists(name):
                break

        state['engine'] = Engine(IMAGE_FOLDER, CSV_FILE, name)
        state['clicked'] = False
        fig, image, text = state['engine'].load_image()

        return (
            gr.update(value=fig, visible=True),
            gr.update(value=image, visible=True),
            gr.update(value=text, visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    with gr.Blocks() as demo:
        state = gr.State({})
        rules = gr.Markdown(RULES, visible=True)

        start_button = gr.Button("Start", visible=True)
        with gr.Row():
            map_ = gr.Image(label='Map', visible=False)
            image_ = gr.Image(label='Image', visible=False)
        with gr.Row():
            text = gr.Markdown("", visible=False)
            text_count = gr.Markdown("", visible=False)

        next_button = gr.Button("Next", visible=False)
        start_button.click(start, inputs=[state], outputs=[map_, image_, text_count, text, next_button, rules, state, start_button])
        map_.select(click, inputs=[state], outputs=[map_, text])
        next_button.click(next_, inputs=[state], outputs=[map_, image_, text_count, text, next_button])

    demo.launch(share=True, debug=True)
