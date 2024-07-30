import json
import os

import openai
from dotenv import load_dotenv
from kafka import KafkaConsumer, KafkaProducer
from langchain import LLMChain, OpenAI, PromptTemplate
from langchain.output_parsers import with_structured_output
from pydantic import BaseModel

# load .env API key
load_dotenv()

# openai key
openai.api_key = os.getenv("OPENAI_API_KEY")


# pydantic class -> Paragraph
class Paragraph(BaseModel):
    content: str


class NameID(BaseModel):
    name: list[str]


# kafka producer for paragraphs
paragraph_consumer = KafkaConsumer(
    "paragraphs",
    bootstrap_servers="localhost:9092",
    auto_offset_reset="earliest",
    enable_auto_commit=True,
    group_id="name-identifier-group",
    value_deserializer=lambda x: json.loads(x.decode("utf-8")),
)

# langchain
llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# kafka producer for names
name_producer = KafkaProducer(
    bootstrap_servers="localhost:9092", value_serializer=lambda v: json.dumps(v).encode("utf-8")
)


# prompt template to feed into langchain
prompt_template = PromptTemplate(
    input_variables=["text"], template="Identify the names in the following text:\n\n{text}\n\nNames:"
)


# LangChain setup
llm = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# chain
chain = LLMChain(llm=llm, prompt=prompt_template, output_parser=with_structured_output(NameID))


def name_identification_with_llm(text):
    response = chain.run({"text": text})
    return response.names


print("Listening for messages on 'paragraphs' topic...")
for message in paragraph_consumer:
    paragraph = Paragraph(**message.value)
    print(f"Received msg : {paragraph.content}")  # debug
    names = name_identification_with_llm(paragraph.content)
    for name in names:
        name_obj = NameID(name=name)
        name_producer.send("identified-names", value=name_obj.dict())
        print(f"Identified name: {name}")
