import streamlit as st
from kafka import KafkaProducer, KafkaConsumer
from pydantic import BaseModel
import json
from youtube_transcript_api import YouTubeTranscriptApi


# pydantic class -> Paragraph
class Paragraph(BaseModel):
    content: str

class NameID(BaseModel):
    name : str


# kafka producer for paragraphs
paragraph_consumer = KafkaConsumer(
    'paragraphs',
    bootstrap_servers='localhost:9092',
    auto_offset_reset='earliest',
    enable_auto_commit=True,
    group_id='name-identifier-group',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)


# kafka producer for names
name_producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)


def name_identification(text):
    words = text.split()
    names = [word for word in words if word.istitle() and not word.isupper()]
    return names


print("Listening for messages on 'paragraphs' topic...")
for message in paragraph_consumer:
    paragraph = Paragraph(**message.value)
    names = name_identification(paragraph.content)
    for name in names:
        name_obj = NameID(name=name)
        name_producer.send('identified-names', value=name_obj.dict())
        print(f"Identified name: {name}")
