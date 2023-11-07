import streamlit as st
import openai
import os
import requests
from PIL import Image
from io import BytesIO
import sqlite3
from datetime import datetime
import pytz

# Define your local timezone
local_tz = pytz.timezone('Asia/Colombo')  # For Sri Lanka

# Function to convert UTC datetime to local timezone
def utc_to_local(utc_dt):
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return local_tz.normalize(local_dt)

# Initialize the database and table if they don't exist
def init_db():
    with sqlite3.connect('dalle_images.db') as conn:
        # Create table if it does not exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt TEXT NOT NULL,
                image_url TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
        ''')
        # Add revised_prompt column if it does not exist
        try:
            conn.execute('ALTER TABLE images ADD COLUMN revised_prompt TEXT')
        except sqlite3.OperationalError:
            # If the error is because the column already exists, it will pass
            pass

# Function to insert a new record into the database
def insert_image(prompt, revised_prompt, image_url):
    with sqlite3.connect('dalle_images.db') as conn:
        conn.execute('INSERT INTO images (prompt, revised_prompt, image_url) VALUES (?, ?, ?)', 
                     (prompt, revised_prompt, image_url))

# Function to get all image records
def get_all_images():
    with sqlite3.connect('dalle_images.db') as conn:
        cur = conn.cursor()
        cur.execute('SELECT prompt, revised_prompt, image_url, timestamp FROM images ORDER BY timestamp DESC')
        return cur.fetchall()

# Set your OpenAI API key (preferably use an environment variable for this)
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initialize database
init_db()

st.title('DALL-E 3 Image Generator')

# Sidebar for navigation
st.sidebar.title("Navigation")
page = st.sidebar.selectbox("Choose a page", ["Generate", "Gallery"])

# Page for image generation
if page == "Generate":
    prompt = st.text_input('Enter the prompt for the image you want to generate:', '')

    if st.button('Generate Image'):
        if prompt:
            try:
                response = openai.Image.create(
                    model="dall-e-3",
                    prompt=prompt,
                    size="1024x1024",
                    quality="standard",
                    n=1,
                )
                image_data = response['data'][0]
                image_url = image_data['url']
                revised_prompt = image_data.get('revised_prompt', 'No revised prompt provided')

                insert_image(prompt, revised_prompt, image_url)

                image_response = requests.get(image_url)
                image = Image.open(BytesIO(image_response.content))
                st.image(image, caption='Generated Image', use_column_width=True)
                st.caption(f"Revised prompt: {revised_prompt}")  # Show the revised prompt under the image

            except Exception as e:
                st.error(f"An error occurred: {e}")
        else:
            st.warning('Please enter a prompt.')

# Page for image gallery
elif page == "Gallery":
    st.title("Image Gallery")

    all_images = get_all_images()
    for idx, (prompt, revised_prompt, image_url, timestamp_str) in enumerate(all_images):
        utc_timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        local_timestamp = utc_to_local(utc_timestamp)

        st.subheader(f"Prompt: {prompt}")
        st.caption(f"Revised Prompt: {revised_prompt}")  # Display the revised prompt in fine print
        st.image(image_url, caption=f"Generated on {local_timestamp.strftime('%Y-%m-%d %H:%M:%S')}", use_column_width=True)
