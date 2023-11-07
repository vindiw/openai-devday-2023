import streamlit as st
import openai
import os
from PIL import Image
import sqlite3
from datetime import datetime
import pytz
from io import BytesIO
import requests

# Define your local timezone
local_tz = pytz.timezone('Asia/Colombo')  # For Sri Lanka

# Function to convert UTC datetime to local timezone
def utc_to_local(utc_dt):
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return local_tz.normalize(local_dt)

def init_db():
    with sqlite3.connect('dalle_images.db') as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                image_binary BLOB,
                image_url TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                revised_prompt TEXT
            );
        ''')
        try:
            conn.execute('ALTER TABLE images ADD COLUMN image_url TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists, ignore

# Modify your insert_image function to accept and store binary image data
def insert_image(prompt, revised_prompt, image_binary, image_url):
    with sqlite3.connect('dalle_images.db') as conn:
        conn.execute('INSERT INTO images (prompt, revised_prompt, image_binary, image_url) VALUES (?, ?, ?, ?)', 
                     (prompt, revised_prompt, image_binary, image_url))

# Function to get all image records
def get_all_images():
    with sqlite3.connect('dalle_images.db') as conn:
        cur = conn.cursor()
        cur.execute('SELECT id, prompt, revised_prompt, image_binary, image_url, timestamp FROM images ORDER BY timestamp DESC')
        return cur.fetchall()

# Set your OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize database
init_db()

# Initialize OpenAI Client
client = openai.OpenAI(api_key=openai.api_key)

st.title('DALL-E 3 Image Generator')

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Choose a page", ["Generate", "Gallery"])

# Page for image generation
if page == "Generate":
    prompt = st.text_input('Enter the prompt for the image you want to generate:', '')
    size = st.selectbox('Select image size:', ['1024x1024', '1024x1792', '1792x1024'])
    quality = st.selectbox('Select image quality:', ['standard', 'hd'])

    if st.button('Generate Image'):
        if prompt:
            try:
                response = client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=1
                )
                # Assuming the response object has a 'data' attribute which is a list of Image objects.
                image_data = response.data[0].url  # This should be the correct way to access the URL
                revised_prompt = getattr(response.data[0], 'revised_prompt', 'No revised prompt provided')

                # Convert image URL to binary data and save as PNG
                image_response = requests.get(image_data)
                image = Image.open(BytesIO(image_response.content))
                buffered = BytesIO()
                image.save(buffered, format="PNG")
                image_binary = buffered.getvalue()

                insert_image(prompt, revised_prompt, image_binary, image_data)  # Pass the image URL here

                st.image(image, caption='Generated Image', use_column_width=True)
                st.caption(f"Revised prompt: {revised_prompt}")

            except Exception as e:
                st.error(f"An error occurred: {e}")

        else:
            st.warning('Please enter a prompt.')

# Page for image gallery
elif page == "Gallery":
    st.title("Image Gallery")

    all_images = get_all_images()
    for idx, (id, prompt, revised_prompt, image_binary, image_url, timestamp_str) in enumerate(all_images):
        if image_binary:
            try:
                image = Image.open(BytesIO(image_binary))
                utc_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                local_timestamp = utc_to_local(utc_timestamp)

                st.subheader(f"Prompt: {prompt}")
                st.caption(f"Revised Prompt: {revised_prompt}")
                st.image(image, caption=f"Generated on {local_timestamp.strftime('%Y-%m-%d %H:%M:%S')}", use_column_width=True)
            except Exception as e:
                st.error(f"Could not load image for prompt: '{prompt}'. Error: {e}")
        else:
            st.info(f"No image data available for prompt: '{prompt}'.")

