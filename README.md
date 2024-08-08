# Kafka-Powered Name Identification and Enrichment System
This project is a distributed system that leverages Kafka, Streamlit, Pydantic, and Cohere via Lamgchain to process and enrich text data.

## Features
* Consume and produce messages using Kafka for real-time processing.
* Identify proper names within paragraphs of text.
* Disambiguate identified names using context.
* Fetch and enrich names with detailed summaries using web search.

## Requirements
- Streamlit for the user interface.
- aiokafka for Kafka integration.
- LangChain and Cohere + web-search connector for name identification and enrichment.
- Pydantic for data validation.

## Installation
Clone the repository:

```sh
git clone https://github.com/dtaibeau/kafka_nameID.git
cd kafka_nameID
```

Install Poetry if you haven't already:

```sh
curl -sSL https://install.python-poetry.org | python3 -
```

Install the dependencies:

```sh
poetry install
```

## Usage
Activate the virtual environment:

```sh
poetry shell
```

## Starting Kafka and Zookeeper
Ensure Kafka and Zookeeper are running, either locally or via Docker.

Run the Streamlit app:
```sh
streamlit run src/app.py
```

Open your web browser and go to http://localhost:8501

## Running the Consumer and Producer Services
```sh
poetry run python src/consumer.py
```

## Using the App
- Input a text paragraph into the provided field.
- Click the "Process Text" button.
- View the enriched names and their summaries on the app interface.

## Project Structure

```plaintext
├── README.md                # README file
├── pyproject.toml           # Poetry configuration file
├── poetry.lock              # Poetry lock file
├── .env                     # Environment variables file
├── .gitignore               # Git ignore file
├── src/                     # Source files/packages
│   ├── consumer.py          # Script for Kafka consumer service
│   ├── producer.py          # Script for Kafka producer service
```

## Future Updates
- Outputting enriched name w/ summary directly to Streamlit app rather than console
- Getting web-search tool to work more consistently.... :')
- Additional features and improvements based on user feedback!!!

:^)








