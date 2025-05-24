import streamlit as st
import json
import os
import boto3
from dotenv import load_dotenv
from config import Config  # Ensure this exists and contains BEDROCK_MODEL_ID

# Load environment variables
load_dotenv()

# Claude 3.7 via Bedrock setup
bedrock = boto3.client(
    service_name="bedrock-runtime",
    region_name=Config.AWS_REGION,
)

def query_claude(prompt: str) -> str:
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "max_tokens": 4000,
        "temperature": 0.2
    })

    response = bedrock.invoke_model(
        modelId=Config.BEDROCK_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response['body'].read())
    return result['content'][0]['text']

def load_all_city_data():
    combined_data = {}
    folder = "output/structured"
    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            with open(os.path.join(folder, filename), "r", encoding="utf-8") as f:
                try:
                    city_data = json.load(f)
                    combined_data[filename] = city_data
                except json.JSONDecodeError:
                    continue
    return combined_data

# Streamlit UI setup
st.set_page_config(page_title="City Data Chatbot", layout="wide")
st.title("🏙️ City Data Chatbot")

if "city_data" not in st.session_state:
    st.session_state.city_data = load_all_city_data()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    if message["role"] == "user":
        st.markdown(f"**🧑 You:** {message['content']}")
    else:
        st.markdown(f"**🤖 Assistant:** {message['content']}")

user_input = st.chat_input("Ask something about the city data...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    context = json.dumps(st.session_state.city_data, indent=2)
    prompt = f"""You are an assistant with access to structured data about various cities.
Here is the combined data:\n\n{context}\n\nAnswer the following question based on this data:\n{user_input}"""

    with st.spinner("Thinking..."):
        response = query_claude(prompt)

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
