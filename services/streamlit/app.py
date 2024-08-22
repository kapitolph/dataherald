import streamlit as st
import requests
import json

# Set the API base URL
API_BASE_URL = "http://localhost/api/v1"

st.title("SQL Query Generator")

def get_database_connections():
    response = requests.get(f"{API_BASE_URL}/database-connections")
    if response.status_code == 200:
        connections = response.json()
        return {conn['alias']: conn['id'] for conn in connections}
    else:
        st.error(f"Failed to fetch database connections: {response.status_code}")
        return {}

def generate_sql(db_connection_id, query_text):
    url = f"{API_BASE_URL}/prompts/sql-generations/nl-generations"
    payload = {
        "llm_config": {
            "llm_name": "gpt-4o-2024-08-06",
            "api_base": ""
        },
        "max_rows": 100,
        "metadata": {},
        "sql_generation": {
            "finetuning_id": "",
            "low_latency_mode": False,
            "llm_config": {
                "llm_name": "gpt-4o-2024-08-06",
                "api_base": ""
            },
            "evaluate": False,
            "metadata": {},
            "prompt": {
                "text": query_text,
                "db_connection_id": db_connection_id,
                "schemas": ["public"],
                "metadata": {}
            }
        }
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    else:
        st.error(f"Failed to generate SQL: {response.status_code}")
        return None

def get_generated_sql(sql_generation_id):
    url = f'{API_BASE_URL}/sql-generations/{sql_generation_id}'
    response = requests.get(url)
    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    else:
        st.error(f'Failed to fetch generated SQL: {response.status_code}')
        return None

# Fetch database connections
db_connections = get_database_connections()

# Create a selection list for database connections
selected_db = st.selectbox("Select Database Connection", list(db_connections.keys()))
selected_db_id = db_connections[selected_db]

# Add a text input for the query
query = st.text_area("Enter your query:", height=100)

# Add a button to generate SQL and display results
if st.button('Generate SQL'):
    if query:
        with st.spinner('Generating SQL...'):
            response = generate_sql(selected_db_id, query)
            print(response)
            if response and 'sql_generation_id' in response:
                sql_generation_id = response['sql_generation_id']
                result = get_generated_sql(sql_generation_id)
                if result:
                    st.subheader('Generated SQL:')
                    st.code(result.get('sql', 'No SQL generated'), language='sql')
                    st.subheader('Results:')
                    st.write(response.get('text', 'No result text available'))
            else:
                st.error('Failed to generate SQL. Please try again.')
    else:
        st.warning('Please enter a query.')