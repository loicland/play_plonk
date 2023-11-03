import os
import tkinter as tk
import pandas as pd
from tkinter import messagebox
from PIL import Image, ImageTk
import reverse_geocoder as rg
import cartopy.crs as ccrs
import cartopy.geodesic as cgeo
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from math import radians, sin, cos, sqrt, asin, exp
import argparse
import pickle

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



class ImageSorter:
    def __init__(self, args, master, images, coordinates, admins):
        self.master = master
        self.images = images
        self.coordinates = coordinates
        self.admins = admins
        self.source_folder = args.image_folder
        self.index = 0     
          
        # Initialize the score and distance lists
        self.scores = []
        self.distances = []
        self.clicked_locations = []

        master.title("Image Viewer")
        self.frame = tk.Frame(master)
        self.frame.pack()

        self.canvas = tk.Canvas(self.frame)
        self.canvas.pack(side="left")

        self.label = tk.Label(self.frame)
        self.label.pack(side="right")
        
        self.result_text_widget = tk.Text(master, height=3, width=100, font=("TkDefaultFont", 10))  # Adjusted for a larger and bigger font text box
        self.result_text_widget.pack()
        
        # Textbox for average score and distance display
        self.average_text_widget = tk.Text(master, height=4   , width=100, font=("TkDefaultFont", 10))
        self.average_text_widget.pack()
        
        # Configure text color tags
        self.result_text_widget.tag_configure('yes_tag', foreground='green')
        self.result_text_widget.tag_configure('no_tag', foreground='red')
        self.result_text_widget.tag_configure('nan_tag', foreground='grey')

        
        # Create the figure and canvas only once
        self.fig = plt.Figure(figsize=(10, 6))
        self.ax = self.fig.add_subplot(1, 1, 1, projection=ccrs.PlateCarree())
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.canvas)
        
        # Textbox for distance display
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack()
        
        #laod pickle - if it exists
        state = self.load_game_state()
        if state is not None:
            self.index = state['index']
            self.scores = state['scores']
            self.distances = state['distances']
            self.clicked_locations = state['clicked_locations']
        else:
            self.index = 0
            self.scores = []
            self.distances = []
            self.clicked_locations = []

        # Load initial image
        self.load_image()
     
    def load_image(self):
        if self.index > len(self.images)-1:
            self.result_text_widget.delete('1.0', tk.END)
            self.result_text_widget.insert('end', "Results processing, please wait")
            
            self.master.update_idletasks()
            self.finish()
            
            self.master.bind('<space>', lambda event: self.exit_application())


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
        
        self.result_text_widget.delete('1.0', tk.END)
        self.result_text_widget.insert('end', f"Image {self.index}/{len(self.images)}\nClick the map")
               
        self.canvas.draw()
        
        self.canvas.mpl_connect('button_press_event', self.on_map_click)
        
    def on_map_click(self, event):
        if event.inaxes:  # Check if click was inside the axes
            click_lon, click_lat = event.xdata, event.ydata
                        
            # Display true location and line
            self.display_true_location_and_line(click_lon, click_lat)

            # Unbind the map click event to avoid multiple clicks
            self.canvas.mpl_disconnect(self.canvas.mpl_connect('button_press_event', self.on_map_click))
        
        
    def display_true_location_and_line(self, click_lon, click_lat):
    # This new method will display the true location and draw the line
    
        self.clicked_locations.append((click_lat,click_lon))
    
        true_lon, true_lat = self.coordinates[self.index]
        self.ax.plot(true_lon, true_lat, 'ro', transform=ccrs.Geodetic())
        
        # Draw geodesic line immediately
        self.ax.plot([true_lon, click_lon], [true_lat, click_lat], 
                    color='blue', linewidth=2, 
                    transform=ccrs.Geodetic())
        
        self.canvas.draw()
        
      
        distance = haversine(true_lat, true_lon, click_lat, click_lon)
        score = geoscore(distance)
        self.scores.append(score)
        self.distances.append(distance)
        
        self.update_average_display()
         
        # Set the text for the label or text variable
        self.result_text_widget.delete('1.0', tk.END)
        result_text = (f"GeoScore: {score:.0f}, "
                       f"distance: {distance:.0f} km\n"
                       "Press space")
        self.result_text_widget.insert('end', result_text)
        
        self.save_game_state(self.index+1, self.scores, self.distances, self.clicked_locations)

        self.master.bind('<space>', self.on_key_press)  
    
    def on_key_press(self, event):
        # Go to the next image on any key press
        self.next_image()

    def next_image(self):
        # Go to the next image
        self.index = (self.index + 1)
        self.load_image()
        
        # Re-bind the map click event for the new image
        self.canvas.mpl_connect('button_press_event', self.on_map_click)

        # Unbind key press to avoid skipping images accidentally
        self.master.unbind('<KeyPress>')
        
        
    def update_average_display(self):
        # Calculate the average values
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0
        avg_distance = sum(self.distances) / len(self.distances) if self.distances else 0

        # Update the text box
        self.average_text_widget.delete('1.0', tk.END)
        self.average_text_widget.insert('end', f"Average GeoScore: {avg_score:.0f}, "
                                               f"Average distance: {avg_distance:.0f} km\n")
    
    def finish(self):
        
        clicks = rg.search(self.clicked_locations)
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
        
        avg_score = sum(self.scores) / len(self.scores) if self.scores else 0
        avg_distance = sum(self.distances) / len(self.distances) if self.distances else 0
        
         # Update the text box
        self.average_text_widget.delete('1.0', tk.END)
        exit_message = (f"Average GeoScore: {avg_score:.0f}, "
                                               f"Average distance: {avg_distance:.0f} km, "
                                               f"Country Acc: {100*avg_country_accuracy:.1f}, "
                                               f"Region Acc: {100*avg_region_accuracy:.1f}, "
                                               f"Area Acc: {100*avg_area_accuracy:.1f}, "
                                               f"City Acc: {100*avg_city_accuracy:.1f}\n"
                                               f"Please copy and paste this line to Loic :)\n"
                                               "Press space to exit")
        self.average_text_widget.insert('end', exit_message)
        
        print(exit_message)
        
    # Function to save the game state
    def save_game_state(self, index, scores, distances, clicked_locations):
        with open('game_state.pkl', 'wb') as f:
            pickle.dump({
                'index': index,
                'scores': scores,
                'distances': distances,
                'clicked_locations': clicked_locations
            }, f)

    # Function to load the game state
    def load_game_state(self):
        if os.path.exists('game_state.pkl'):
            with open('game_state.pkl', 'rb') as f:
                return pickle.load(f)
        return None  # Return None or default values if the file does not exist
    
        
    def exit_application(self):
        print("bye")
        self.master.unbind('<space>')
        # Destroy the main window and exit the application
        self.master.destroy()   

def load_images_and_coordinates(csv_file):
    # Load the CSV
    df = pd.read_csv(csv_file)

    # Get the image filenames and their coordinates
    image_ids = df['image_id'].tolist()
    coordinates = df[['longitude', 'latitude']].values.tolist()
    admins = df[['city', 'area', 'region', 'country']].values.tolist()

    return image_ids[:], coordinates[:], admins[:]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Image Viewer with Map')
    parser.add_argument('--image_folder', type=str, required=False, help='Folder with images', default='./select')
    parser.add_argument('--csv_file', type=str, required=False, help='CSV file with image ids and coordinates', default='./select.csv')

    args = parser.parse_args()
       
    images, coordinates, admins = load_images_and_coordinates(args.csv_file)

    root = tk.Tk()
    root.tk.call('tk', 'scaling', 4.0)  # Adjust the 4.0 to whatever scale factor is needed for your display

    app = ImageSorter(args, root, images, coordinates, admins)

    root.mainloop()
    
    
