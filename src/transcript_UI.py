import streamlit as st
from kafka import KafkaProducer
from pydantic import BaseModel
import json
from youtube_transcript_api import YouTubeTranscriptApi

# pydantic class
class Paragraph(BaseModel):
    content: str

# split into paragraphs
def split_transcript(transcript):
    paragraphs = transcript.split('\n\n')
    return [Paragraph(content=p) for p in paragraphs if p.strip()]

# kafka producer
producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# fetch transcrpt from yt url
def fetch_youtube_transcript(video_url):
    video_id = video_url.split("v=")[1]
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    transcript_text = " ".join([item['text'] for item in transcript_list])
    return transcript_text

# streamlit setup
st.title('Transcript Input Service')
input_option = st.radio(
    "Choose input method:",
    ("Copy/Paste", "File Upload", "YouTube URL")
)

transcript = ""

if input_option == "Copy/Paste":
    transcript = st.text_area('Enter the transcript:')
elif input_option == "File Upload":
    uploaded_file = st.file_uploader("Choose a file")
    if uploaded_file is not None:
        transcript = uploaded_file.read().decode("utf-8")
elif input_option == "YouTube URL":
    url = st.text_input('Enter the YouTube URL:')
    if url:
        try:
            transcript = fetch_youtube_transcript(url)
            st.success('Transcript fetched successfully from YouTube!')
        except Exception as e:
            st.error(f"Error fetching transcript: {e}")

if transcript and st.button('Send to Kafka'):
    paragraphs = split_transcript(transcript)
    for paragraph in paragraphs:
        serialized_paragraph = paragraph.dict()  # serialize w/ pydantic
        producer.send('paragraphs', value=serialized_paragraph)
    st.success('Transcript sent to Kafka!')
