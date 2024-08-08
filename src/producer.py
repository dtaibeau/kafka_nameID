import asyncio
import json

import streamlit as st
from aiokafka import AIOKafkaProducer
from dotenv import load_dotenv
from pydantic.v1 import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi

# api key
load_dotenv()


# pydantic classes
class Paragraph(BaseModel):
    content: str


class BasicEnrichment(BaseModel):
    name: str
    summary: str


# split into paragraphs
def split_transcript(content):
    paragraphs = content.split("\n\n")
    return [Paragraph(content=p) for p in paragraphs if p.strip()]


# kafka producer for paragraphs
async def send_paragraphs_to_kafka(paragraphs):
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092", value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )
    await producer.start()
    try:
        for paragraph in paragraphs:
            serialized_paragraph = paragraph.dict()
            await producer.send("paragraphs", value=serialized_paragraph)
        await producer.flush()
    finally:
        await producer.stop()


# fetch yt url transcript
def fetch_youtube_transcript(video_url):
    video_id = video_url.split("v=")[1]
    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
    transcript_text = " ".join([item["text"] for item in transcript_list])
    return transcript_text


# streamlit setup
st.title("Transcript Input Service")
input_option = st.radio("Choose input method:", ("Copy/Paste", "File Upload", "YouTube URL"))

transcript = ""

if input_option == "Copy/Paste":
    transcript = st.text_area("Enter the transcript:")
elif input_option == "File Upload":
    uploaded_file = st.file_uploader("Choose a file")
    if uploaded_file is not None:
        transcript = uploaded_file.read().decode("utf-8")
elif input_option == "YouTube URL":
    url = st.text_input("Enter the YouTube URL:")
    if url:
        try:
            transcript = fetch_youtube_transcript(url)
            st.success("Transcript fetched successfully from YouTube!")
        except Exception as e:
            st.error(f"Error fetching transcript: {e}")

if transcript and st.button("Send to Kafka"):
    paragraphs = split_transcript(transcript)
    asyncio.run(send_paragraphs_to_kafka(paragraphs))
    st.success("Transcript sent to Kafka!")
