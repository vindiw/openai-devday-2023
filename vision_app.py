import streamlit as st
from PIL import Image
import requests
import base64
import io
import os
import sqlite3
import uuid
from datetime import datetime
from pytz import timezone

# Function to convert UTC to local time
def localize_timestamp(utc_dt):
    local_tz = timezone('Asia/Colombo')  # Change this as needed
    local_dt = utc_dt.replace(tzinfo=timezone('UTC')).astimezone(local_tz)
    return local_tz.normalize(local_dt)  # .normalize might be unnecessary depending on your use case

# Function to encode image to base64, handling PNG with transparency
def encode_image(image):
    buffered = io.BytesIO()
    if image.mode in ("RGBA", "LA"):
        background = Image.new(image.mode[:-1], image.size, (255, 255, 255))
        background.paste(image, image.split()[-1])
        image = background.convert("RGB")
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# Function to make API call to OpenAI
def ask_openai(base64_image, question):
    openai_api_key = os.getenv('OPENAI_API_KEY')
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai_api_key}"
    }
    payload = {
        "model": "gpt-4-vision-preview",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }
        ],
        "max_tokens": 300
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    return response.json()

# Initialize SQLite DB
def init_db():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS queries
                 (date TEXT, prompt TEXT, response TEXT, image_path TEXT)''')
    conn.commit()
    conn.close()

# Modify the insert_record function to save files with unique names and write bytes
def insert_record(prompt, response, base64_image):
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    unique_filename = f'image_{uuid.uuid4()}.jpeg'
    image_data = base64.b64decode(base64_image)
    with open(unique_filename, 'wb') as f:
        f.write(image_data)
    c.execute("INSERT INTO queries VALUES (datetime('now'), ?, ?, ?)",
              (prompt, response, unique_filename))
    conn.commit()
    conn.close()
    return unique_filename

# Function to get records from the SQLite DB
def get_records():
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("SELECT date, prompt, response, image_path FROM queries ORDER BY date DESC")
    records = c.fetchall()
    conn.close()
    return records

# Initialize database
init_db()

# Check for run_id in session state or initialize it
if 'run_id' not in st.session_state:
    st.session_state['run_id'] = str(uuid.uuid4())

# Streamlit UI
st.title('🖼️ GPT-4 Vision Explorer 🔍')

# Image upload
uploaded_file = st.file_uploader("Choose an image...", type=["jpg", "jpeg", "png"])
if uploaded_file is not None:
    image = Image.open(uploaded_file)
    st.image(image, caption='Uploaded Image', use_column_width=True)
    st.write("Image successfully uploaded!")
    base64_image = encode_image(image)

    # Text input for question
    question = st.text_input("What would you like to ask about the image?")

    if st.button('Ask GPT-4 Vision'):
        if question:
            with st.spinner('GPT-4 is at work...'):
                response = ask_openai(base64_image, question)

                if 'choices' in response:
                    content = response['choices'][0]['message']['content']
                    st.write(content)

                    # Call the insert_record function with base64_image and save the unique path returned
                    unique_image_path = insert_record(question, content, base64_image)

                    # Display the image using the unique path
                    st.image(unique_image_path, caption='Uploaded Image', use_column_width=True)

                    # Optional: Clean up the temp file if needed
                    # os.remove(unique_image_path)

                else:
                    st.error("Unexpected response structure, check the API response.")
        else:
            st.error('Please enter a question.')

else:
    st.warning('Please upload an image to get started.')

# Display the records from the SQLite DB in the Streamlit UI, now with local time
st.header("Previous Queries")
records = get_records()
for record in records:
    # Convert the stored UTC time to local time
    utc_time = datetime.strptime(record[0], '%Y-%m-%d %H:%M:%S')
    local_time = localize_timestamp(utc_time).strftime('%Y-%m-%d %H:%M:%S %Z%z')
    st.text(f"Date: {local_time}")
    st.text(f"Prompt: {record[1]}")
    st.text(f"Response: {record[2]}")
    image_path = record[3]
    if os.path.exists(image_path):
        st.image(image_path, caption='Uploaded Image', use_column_width=True)
    else:
        st.error("Image not found.")