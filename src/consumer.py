import asyncio
import json
import os
import re

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from dotenv import load_dotenv
from langchain_cohere import ChatCohere
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)
from loguru import logger
from pydantic.v1 import BaseModel

### SETUP ###

# load .env key
load_dotenv(".env")

# cohere setup
cohere_api_key = os.getenv("COHERE_API_KEY")
if not cohere_api_key:
    raise ValueError("COHERE_API_KEY not found in environment variables")

# langchain_api_key = os.getenv("LANGCHAIN_API_KEY")
# if not langchain_api_key:
#     raise ValueError("LANGCHAIN_API_KEY not found in environment variables")


# initializing cohere chat model
cohere_chat_model = ChatCohere(cohere_api_key=cohere_api_key, connectors=[{"id": "web-search"}])

# creating cohere rag retriever w/ web search connector
# rag = CohereRagRetriever(llm=cohere_chat_model, connectors=[{"id": "web-search"}])


# pydantic classes
class Paragraph(BaseModel):
    content: str


class IdentifiedName(BaseModel):
    name: str
    context: str


class BasicEnrichment(BaseModel):
    name: str
    summary: str


### NAME IDENTIFICATION ###


# step 1) extract from paragraph
async def identify_names_from_paragraph(paragraph):
    response = await cohere_chat_model.agenerate(
        messages=[
            [
                SystemMessage(
                    content="You are a human name identifier specializing in " "identifying well-known individuals."
                ),
                HumanMessage(
                    content=f"Please list all the proper names in the following paragraph:\n\n{paragraph}\n\n"
                    f"Separate the names with commas."
                ),
            ]
        ]
    )

    # extract names from response
    first_generation = response.generations[0]
    if isinstance(first_generation, list):
        first_generation = first_generation[0]
    identified_names_text = (
        first_generation.message.content.strip()
        if hasattr(first_generation, "message")
        else first_generation.text.strip()
    )

    # split names into list
    identified_names = [name.strip() for name in identified_names_text.split(",") if name.strip()]

    return identified_names


# step 2) disambiguate names from surrounding context
async def name_disambiguation(names, context):
    logger.info(f"Starting name disambiguation for names: {names}")

    disambiguated_names = []
    for name in names:
        if len(name.split()) == 1:
            disambiguation_prompt = (
                f"You are a name identifier. The term '{name}' is ambiguous. Try to use the context in conversation "
                f"to disambiguate them so that even if only a partial name is given, you can deduce their "
                f"full name and claim to fame. Answer with JSON. For each name, answer only once."
            )

            user_message = f"This is the surrounding context of the name in question: {context}\n\n"

            response = await cohere_chat_model.agenerate(
                messages=[
                    [
                        SystemMessage(content=disambiguation_prompt),
                        HumanMessage(content=user_message),
                    ]
                ]
            )

            post_disambiguation_response = (
                response.generations[0][0].message.content.strip()
                if hasattr(response.generations[0][0], "message")
                else response.generations[0][0].text.strip()
            )

            print("Cohere Response After Disambiguating:", post_disambiguation_response)

            # clean up and parse json response
            try:
                cleaned_response = re.sub(r"```json\n|\n```", "", post_disambiguation_response)
                disambiguated_names_json = json.loads(cleaned_response)
                for item in disambiguated_names_json:
                    disambiguated_name = item["name"]
                    disambiguated_names.append(disambiguated_name)
                    print(disambiguated_names)
            except json.JSONDecodeError as e:
                print("Failed to decode JSON response from Cohere:", e)
        else:
            disambiguated_names.append(name)

    return disambiguated_names


### PROMPTS + CHAINING ###


SYSTEM_PROMPT = SystemMessagePromptTemplate.from_template(
    """You are a web search expert. The term '{name}' requires further information. Please provide a detailed 
            summary of the individual including their major accomplishments and why they are well-known."""
)
USER_PROMPT = HumanMessagePromptTemplate.from_template(
    """Please provide a 3 sentence summary for {name} containing details about interesting things they did in 2024."""
)

prompt = ChatPromptTemplate.from_messages([SYSTEM_PROMPT, USER_PROMPT])
chain = (prompt | cohere_chat_model.with_structured_output(BasicEnrichment)).with_config(
    {"run_name": "name_enrichment"}
)


# step 3) fetch summary based on disambiguated name using web-search connector
async def fetch_summary_using_web_search(name: str):
    logger.info(f"Fetching summary for name: {name}")

    try:
        print("Invoking web search")
        docs = await chain.ainvoke(dict(name=name))
        print("Raw result before BasicEnrichment handling:", docs)
        print("After ainvoke call")

        logger.info(f"Web search raw result: {docs}")

        if isinstance(docs, BasicEnrichment):
            summary = docs.summary
        else:
            summary = "No summary found."
        return summary

    except Exception as e:
        logger.error(f"Error during web search: {e}")
        return f"Error fetching summary for {name}: {e}"


### KAFKA SYSTEM ###


# I: paragraphs
# O: identified-names
async def name_enrichment_service():
    logger.info("Starting name_enrichment_service")

    # kafka consumer for identified names
    consumer = AIOKafkaConsumer(
        "identified-names",
        bootstrap_servers="localhost:9092",
        group_id="name-enrichment-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    # kafka producer for enriched names
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    await consumer.start()
    await producer.start()

    try:
        async for message in consumer:
            name_data = IdentifiedName(**message.value)
            context = name_data.context
            logger.info("Received name data with context")

            disambiguated_names = await name_disambiguation([name_data.name], context)
            logger.info(f"Disambiguated names: {disambiguated_names}")

            for name in disambiguated_names:
                summary = await fetch_summary_using_web_search(name)

                enriched_name_data = BasicEnrichment(name=name, summary=summary).dict()
                logger.info(f"Sending summary with name to Kafka: {enriched_name_data}")
                await producer.send("enriched-names", value=enriched_name_data)

    except Exception as e:
        logger.error(f"Error in consuming messages: {e}")
    finally:
        await consumer.stop()
        await producer.stop()


# I: identified-names
# O: enriched-names
async def identify_names_service():
    logger.info("Starting identify_names_service")
    # kafka consumer for paragraphs
    consumer = AIOKafkaConsumer(
        "paragraphs",
        bootstrap_servers="localhost:9092",
        group_id="name-identifier-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    # kafka producer for identified names
    producer = AIOKafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    await consumer.start()
    await producer.start()

    try:
        async for message in consumer:
            paragraph = message.value.get("content")
            logger.info("Received paragraph")

            identified_names = await identify_names_from_paragraph(paragraph)

            for name in identified_names:
                name_data = IdentifiedName(name=name, context=paragraph).dict()
                logger.info("Sending identified name with context to Kafka")

                await producer.send("identified-names", value=name_data)
    except Exception as e:
        logger.error(f"Error in consuming messages: {e}")

    finally:
        await consumer.stop()
        await producer.stop()


# I: enriched-names
# O: None
async def name_presentation_service():
    # kafka consumer for enriched names
    consumer = AIOKafkaConsumer(
        "enriched-names",
        bootstrap_servers="localhost:9092",
        group_id="name-presentation-group",
        value_deserializer=lambda x: json.loads(x.decode("utf-8")),
    )

    await consumer.start()

    try:
        async for message in consumer:
            name_data = BasicEnrichment(**message.value)
            print(f"Enriched name received from Kafka: {name_data.name} - Summary: {name_data.summary}")

    except Exception as e:
        print(f"Error in consuming messages: {e}")
    finally:
        await consumer.stop()


async def main():
    await asyncio.gather(identify_names_service(), name_enrichment_service())


if __name__ == "__main__":
    asyncio.run(main())
