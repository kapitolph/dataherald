import streamlit as st
import requests
import json
import pandas as pd
from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv
import time
import math

load_dotenv()

st.set_page_config(page_title="Dataherald", page_icon="🤖", layout="wide")

# Set the API base URL
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost/api/v1")

def main():
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Admin"])

    if page == "Home":
        sql_query_generator()
    elif page == "Admin":
        admin_page()

def estimate_cost(tokens_used, model="gpt-4o-2024-08-06"):
    # Updated pricing per 1000 tokens
    pricing = {
        "gpt-4o-2024-08-06": {"input": 0.00250, "output": 0.01000},
    }
    
    if model not in pricing:
        return None
    
    # Assuming an even split between input and output tokens
    # You may want to adjust this ratio based on your actual usage
    input_tokens = tokens_used // 2
    output_tokens = tokens_used - input_tokens
    
    cost = (input_tokens * pricing[model]["input"] / 1000) + (output_tokens * pricing[model]["output"] / 1000)
    return cost

def sql_query_generator():
    st.title("Ask Me Anything")

    db_connections = get_database_connections()

    if not db_connections:
        st.warning("No database connections available. Please add a database connection in the Admin page.")
        return

    connection_options = [f"{conn.get('alias', 'No Alias')} (ID: {conn.get('id', 'No ID')})" for conn in db_connections]
    
    if not connection_options:
        st.warning("No valid database connections found.")
        return

    selected_conn = st.selectbox("Select Database Connection", connection_options)
    selected_db_id = selected_conn.split("(ID: ")[-1].strip(")")

    # Initialize session state for query if it doesn't exist
    if 'query' not in st.session_state:
        st.session_state.query = ""

    # Use the stored query to initialize the text area
    query = st.text_area("Enter your query:", value=st.session_state.query, height=100, key="query_input")
    
    # Update the stored query when the user types
    st.session_state.query = query

    if st.button('Generate SQL'):
        if not query:
            st.error('Please enter a query.')
            return

        with st.spinner('Generating SQL...'):
            response = generate_sql(selected_db_id, query)
            if response and 'sql_generation_id' in response:
                sql_generation_id = response['sql_generation_id']
                result = get_generated_sql(sql_generation_id)
                if result:
                    st.subheader('Results:')
                    st.write(response.get('text', 'No result text available'))
                    st.subheader('Generated SQL:')
                    st.code(result.get('sql', 'No SQL generated'), language='sql')

                    # Display tokens used
                    tokens_used = result.get('tokens_used')
                    if tokens_used is not None:
                        st.info(f"Tokens used: {tokens_used}")
                
                        estimated_cost = estimate_cost(tokens_used, "gpt-4o-2024-08-06")
                        if estimated_cost is not None:
                            st.info(f"Estimated cost: ${estimated_cost:.5f}")
            else:
                st.error('Failed to generate SQL. Please try again.')
    
def admin_page():
    st.title("Admin Page")

    admin_option = st.sidebar.selectbox(
        "Choose an option",
        ["Database Connections", "Sync Database Schema", "Manage Golden SQLs", "Manage Table Descriptions", "Manage DB Instructions"]
    )

    if admin_option == "Database Connections":
        database_connections_page()
    elif admin_option == "Sync Database Schema":
        sync_database_schema()
    elif admin_option == "Manage Golden SQLs":
        manage_golden_sqls()
    elif admin_option == "Manage Table Descriptions":
        manage_table_descriptions()
    elif admin_option == "Manage DB Instructions":
        manage_db_instructions()

def database_connections_page():
    st.header("Database Connections")
    
    with st.expander("List Database Connections", expanded=True):
        list_database_connections()
    
    with st.expander("Add New Connection"):
        add_database_connection()
    
    with st.expander("Edit Existing Connection"):
        st.write("Temporarily disabled.")
        # edit_database_connection_selector()

def list_database_connections():
    connections = get_database_connections()
    
    if not connections:
        st.info("No database connections found.")
        return

    df = pd.DataFrame(connections)
    df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    display_columns = {
        'alias': 'Alias',
        'id': 'ID',
        'dialect': 'Dialect',
        'created_at': 'Created At'
    }
    df_display = df[list(display_columns.keys())].rename(columns=display_columns)

    search_term = st.text_input("Search connections", "")
    if search_term:
        df_display = df_display[df_display['Alias'].str.contains(search_term, case=False)]

    st.dataframe(df_display, use_container_width=True)

def add_database_connection():
    st.subheader("Add New Database Connection")

    alias = st.text_input("Alias")
    connection_uri = st.text_input("Connection URI")
    schemas_text = st.text_input("Schemas (comma-separated)", value="public")

    if st.button("Add Connection"):
        if not alias or not connection_uri:
            st.error("Please fill in both Alias and Connection URI.")
        elif check_alias_exists(alias):
            st.error(f"The alias '{alias}' already exists. Please choose a different alias.")
        else:
            with st.spinner("Adding database connection..."):
                default_llm_api_key = os.getenv("DEFAULT_LLM_API_KEY")
                if not default_llm_api_key:
                    st.error("DEFAULT_LLM_API_KEY not found in environment variables.")
                    return
                
                schemas = [s.strip() for s in schemas_text.split(',') if s.strip()]
                if not schemas:
                    schemas = ["public"]
                
                payload = {
                    "alias": alias,
                    "connection_uri": connection_uri,
                    "llm_api_key": default_llm_api_key,
                    "schemas": schemas
                }
                try:
                    response = requests.post(f"{API_BASE_URL}/database-connections", json=payload)
                    if response.status_code in [200, 201]:
                        time.sleep(1)
                        st.success("Database connection added successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to add database connection: {response.status_code}")
                        st.error(f"Error message: {response.text}")
                except requests.RequestException as e:
                    st.error(f"An error occurred while adding the connection: {str(e)}")

def edit_database_connection_selector():
    connections = get_database_connections()
    selected_connection = st.selectbox("Select a connection to edit", 
                                       [""] + [conn['alias'] for conn in connections])
    if selected_connection:
        connection = next((conn for conn in connections if conn['alias'] == selected_connection), None)
        if connection:
            edit_database_connection(connection)

def edit_database_connection(connection):
    st.subheader(f"Edit Database Connection: {connection['alias']}")

    st.write(f"ID: {connection['id']}")
    alias = st.text_input("Alias", value=connection['alias'], key="edit_alias")
    
    # Use session state to maintain the decrypted URI and verification status
    if 'decrypted_uri' not in st.session_state:
        st.session_state.decrypted_uri = None
    if 'key_verified' not in st.session_state:
        st.session_state.key_verified = False

    # Request encryption key from user
    encryption_key = st.text_input("Enter encryption key to view/edit connection URI", type="password")
    
    if st.button("Verify Key"):
        if encryption_key:
            try:
                st.session_state.decrypted_uri = decrypt_value_with_key(connection['connection_uri'], encryption_key)
                st.session_state.key_verified = True
                st.success("Encryption key verified. You can now view and edit the connection URI.")
            except Exception as e:
                st.error("Invalid encryption key or unable to decrypt.")
                st.session_state.key_verified = False
                st.session_state.decrypted_uri = None
        else:
            st.warning("Please enter an encryption key.")

    if st.session_state.key_verified:
        connection_uri = st.text_input("Connection URI", value=st.session_state.decrypted_uri, type="password", key="edit_connection_uri")
    else:
        st.warning("Verify the encryption key to view and edit the connection URI.")
        connection_uri = None
    
    # Get existing schemas, handle different possible types
    existing_schemas = connection.get('schemas', [])
    if isinstance(existing_schemas, str):
        schemas_text = existing_schemas
    elif isinstance(existing_schemas, list):
        schemas_text = ','.join(str(s) for s in existing_schemas)
    else:
        schemas_text = 'public'  # Default to 'public' if schemas is neither string nor list
    
    # Allow editing of existing schemas and adding new ones
    schemas_text = st.text_input("Schemas (comma-separated)", value=schemas_text, key="edit_schemas")

    if st.button("Update Connection", key="edit_update_button"):
        if not alias:
            st.error("Please fill in the Alias.")
        elif not st.session_state.key_verified or not connection_uri:
            st.error("Please enter the correct encryption key to view and edit the Connection URI.")
        else:
            with st.spinner("Updating database connection..."):
                default_llm_api_key = os.getenv("DEFAULT_LLM_API_KEY")
                if not default_llm_api_key:
                    st.error("DEFAULT_LLM_API_KEY not found in environment variables.")
                    return
                
                schemas = [s.strip() for s in schemas_text.split(',') if s.strip()]
                if not schemas:
                    schemas = ["public"]
                
                updated_data = {
                    "alias": alias,
                    "use_ssh": False,
                    "connection_uri": connection_uri,
                    "schemas": schemas,
                    "llm_api_key": default_llm_api_key,
                    "metadata": {},
                    "path_to_credentials_file": "",
                    "ssh_settings": {}
                }
                
                try:
                    response = requests.put(f"{API_BASE_URL}/database-connections/{connection['id']}", json=updated_data)
                    if response.status_code == 200:
                        time.sleep(1)
                        st.success("Connection updated successfully!")

                        # Reset session state
                        for key in list(st.session_state.keys()):
                            del st.session_state[key]

                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to update connection: {response.status_code}")
                        st.error(f"Error message: {response.text}")
                except requests.RequestException as e:
                    st.error(f"An error occurred while updating the connection: {str(e)}")

def decrypt_value_with_key(encrypted_value, key):
    if not encrypted_value:
        return ""
    try:
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_value.encode())
        return decrypted.decode()
    except Exception as e:
        raise Exception(f"Unable to decrypt: {str(e)}")

def check_alias_exists(alias):
    response = requests.get(f"{API_BASE_URL}/database-connections")
    if response.status_code == 200:
        connections = response.json()
        return any(conn['alias'].lower() == alias.lower() for conn in connections)
    else:
        st.error(f"Failed to check existing aliases: {response.status_code}")
        return False

def sync_database_schema():
    st.header("Sync Database Schema")

    st.info("""
    The database scan is used to gather information about the database including table and column names 
    and identifying low cardinality columns and their values. This information is stored in the context 
    store and used in the prompts to the LLM.
    """)
    
    db_connections = get_database_connections()
    
    if not db_connections:
        st.warning("No database connections available. Please add a database connection first.")
        return

    selected_db = st.selectbox("Select Database Connection", [""] + [conn['alias'] for conn in db_connections])
    
    if not selected_db:
        st.info("Please select a database connection to proceed.")
        return

    selected_db_id = next((conn['id'] for conn in db_connections if conn['alias'] == selected_db), None)

    with st.spinner("Fetching table descriptions..."):
        response = requests.get(f"{API_BASE_URL}/table-descriptions", params={"db_connection_id": selected_db_id})
    
    if response.status_code == 200:
        table_descriptions = response.json()
        if not table_descriptions:
            st.info("No tables found for this database connection.")
            return
        
        table_names = [td['table_name'] for td in table_descriptions]
        
        select_all = st.checkbox("Select All")
        search_term = st.text_input("Search tables", "")
        filtered_tables = [name for name in table_names if search_term.lower() in name.lower()]
        
        selected_tables = st.multiselect("Select tables to sync", filtered_tables, default=filtered_tables if select_all else [])
        
        selected_table_ids = [td['id'] for td in table_descriptions if td['table_name'] in selected_tables]
        
        if st.button("Sync Selected Tables"):
            if not selected_tables:
                st.error("Please select at least one table to sync.")
            else:
                with st.spinner("Syncing database schema..."):
                    payload = {
                        "ids": selected_table_ids,
                        "metadata": {}
                    }
                    sync_response = requests.post(f"{API_BASE_URL}/table-descriptions/sync-schemas", json=payload)
                    if sync_response.status_code in [200, 201]:
                        time.sleep(1)
                        st.success("Database schema synced successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to sync database schema: {sync_response.status_code}")
                        st.error(f"Error message: {sync_response.text}")
                        if "connection" in sync_response.text.lower():
                            st.info("Tip: Check your database connection and try again.")
                        elif "permission" in sync_response.text.lower():
                            st.info("Tip: Ensure you have the necessary permissions to perform this action.")
    else:
        st.error(f"Failed to fetch table descriptions: {response.status_code}")
        st.error(f"Error message: {response.text}")

def manage_golden_sqls():
    st.header("Manage Golden SQLs")

    st.info("""
    Adding ground truth Question/SQL pairs is a powerful way to improve the accuracy of the generated SQL. 
    Golden records can be used either to fine-tune the LLM or to augment the prompts to the LLM.
    """)

    # Fetch database connections
    db_connections = get_database_connections()
    if not db_connections:
        st.warning("No database connections available. Please add a database connection first.")
        return

    # Select database connection
    selected_db = st.selectbox(
        "Select Database Connection",
        options=[""] + [conn['alias'] for conn in db_connections],
        format_func=lambda x: "Select a database connection" if x == "" else x
    )

    if not selected_db:
        st.info("Please select a database connection to manage Golden SQLs.")
        return

    selected_db_id = next((conn['id'] for conn in db_connections if conn['alias'] == selected_db), None)

    # Fetch Golden SQLs for the selected database
    response = requests.get(f"{API_BASE_URL}/golden-sqls", params={"db_connection_id": selected_db_id})
    if response.status_code != 200:
        st.error(f"Failed to fetch Golden SQLs: {response.status_code}")
        return

    golden_sqls = response.json()

    # Display existing Golden SQLs
    with st.expander("Existing Golden SQLs", expanded=True):
        if not golden_sqls:
            st.info("No Golden SQLs found for this connection.")
        else:
            search_term = st.text_input("Search Golden SQLs", "")
            filtered_sqls = [sql for sql in golden_sqls if search_term.lower() in sql['prompt_text'].lower()]
            
            for sql in filtered_sqls:
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"**Prompt:** {sql['prompt_text']}")
                    st.code(sql['sql'], language='sql')
                with col2:
                    if st.button("Delete", key=f"delete_{sql['id']}"):
                        delete_golden_sql(sql['id'])
                st.markdown("---")

    # Form to add new Golden SQL
    st.subheader("Add New Golden SQL")
    with st.form("add_golden_sql"):
        prompt_text = st.text_area("Prompt Text")
        sql = st.text_area("SQL Query")
        submit_button = st.form_submit_button("Add Golden SQL")

        if submit_button:
            if not prompt_text or not sql:
                st.error("Please fill in both Prompt Text and SQL Query.")
            else:
                with st.spinner("Adding Golden SQL..."):
                    payload = [{
                        "db_connection_id": selected_db_id,
                        "prompt_text": prompt_text,
                        "sql": sql,
                        "metadata": {}
                    }]
                    response = requests.post(f"{API_BASE_URL}/golden-sqls", json=payload)
                    if response.status_code in [200, 201]:
                        time.sleep(1)
                        st.success("Golden SQL added successfully!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to add Golden SQL: {response.status_code}")
                        st.error(f"Error message: {response.text}")

def delete_golden_sql(golden_sql_id):
    with st.spinner("Deleting Golden SQL..."):
        response = requests.delete(f"{API_BASE_URL}/golden-sqls/{golden_sql_id}")
        if response.status_code == 200:
            time.sleep(1)
            st.success("Golden SQL deleted successfully!")
            time.sleep(1)
            st.rerun()
        else:
            st.error(f"Failed to delete Golden SQL: {response.status_code}")
            st.error(f"Error message: {response.text}")

def manage_table_descriptions():
    st.header("Manage Table Descriptions")

    st.info("""
    In addition to database table_info and golden_sql, you can set descriptions or update the columns 
    per table and column. Descriptions are used by the agents to determine the relevant columns and 
    tables to the user's question.
    """)

    db_connections = get_database_connections()
    if not db_connections:
        st.warning("No database connections available. Please add a database connection first.")
        return

    selected_db = st.selectbox(
        "Select Database Connection",
        options=[""] + [conn['alias'] for conn in db_connections],
        format_func=lambda x: "Select a database connection" if x == "" else x
    )

    if not selected_db:
        st.info("Please select a database connection to manage table descriptions.")
        return

    selected_db_id = next((conn['id'] for conn in db_connections if conn['alias'] == selected_db), None)

    # Fetch table descriptions
    response = requests.get(f"{API_BASE_URL}/table-descriptions", params={"db_connection_id": selected_db_id})
    if response.status_code != 200:
        st.error(f"Failed to fetch table descriptions: {response.status_code}")
        return

    table_descriptions = response.json()

    if not table_descriptions:
        st.info("No table descriptions found for this connection.")
        return

    # Search functionality
    search_term = st.text_input("Search tables", "")
    if search_term:
        table_descriptions = [table for table in table_descriptions if search_term.lower() in table['table_name'].lower()]

    # Pagination
    items_per_page = 10
    total_pages = math.ceil(len(table_descriptions) / items_per_page)
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        page = st.selectbox("Page", options=range(1, total_pages + 1))

    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    current_tables = table_descriptions[start_idx:end_idx]

    st.write(f"Showing {len(current_tables)} of {len(table_descriptions)} tables")

    # Display and edit table descriptions
    for table in current_tables:
        with st.expander(f"Table: {table['table_name']}", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_description = st.text_area("Description", value=table.get('description', ''), key=f"desc_{table['id']}")
            with col2:
                if st.button("Update", key=f"update_{table['id']}"):
                    update_table_description(table['id'], new_description)

    # Pagination controls
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("First", disabled=page==1):
            page = 1
    with col2:
        if st.button("Previous", disabled=page==1):
            page -= 1
    with col3:
        st.write(f"Page {page} of {total_pages}")
    with col4:
        if st.button("Next", disabled=page==total_pages):
            page += 1
    with col5:
        if st.button("Last", disabled=page==total_pages):
            page = total_pages

def update_table_description(table_id, new_description):
    url = f"{API_BASE_URL}/table-descriptions/{table_id}"
    payload = {"description": new_description}
    response = requests.put(url, json=payload)
    if response.status_code == 200:
        st.success("Table description updated successfully!")
    else:
        st.error(f"Failed to update table description: {response.status_code}")
        st.error(f"Error message: {response.text}")

def manage_db_instructions():
    st.header("Manage Database-Level Instructions")

    st.info("""
    Database level instructions are passed directly to the engine and can be used to steer the engine 
    to generate SQL that is more in line with your business logic. This can include instructions such as 
    "never use this column in a where clause" or "always use this column in a where clause".
    """)

    db_connections = get_database_connections()
    if not db_connections:
        st.warning("No database connections available. Please add a database connection first.")
        return

    selected_db = st.selectbox(
        "Select Database Connection",
        options=[""] + [conn['alias'] for conn in db_connections],
        format_func=lambda x: "Select a database connection" if x == "" else x
    )

    if not selected_db:
        st.info("Please select a database connection to manage instructions.")
        return

    selected_db_id = next((conn['id'] for conn in db_connections if conn['alias'] == selected_db), None)

    # Fetch existing instructions
    response = requests.get(f"{API_BASE_URL}/instructions", params={"db_connection_id": selected_db_id})
    if response.status_code == 200:
        instructions = response.json()
    else:
        st.error(f"Failed to fetch instructions: {response.status_code}")
        return

    # Display existing instructions
    st.subheader("Existing Instructions")
    for instruction in instructions:
        with st.expander(f"Instruction {instruction['id']}", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                new_instruction = st.text_area("Instruction", value=instruction['instruction'], key=f"instr_{instruction['id']}")
            with col2:
                if st.button("Update", key=f"update_{instruction['id']}"):
                    update_instruction(instruction['id'], new_instruction)
                if st.button("Delete", key=f"delete_{instruction['id']}"):
                    delete_instruction(instruction['id'])

    # Add new instruction
    st.subheader("Add New Instruction")
    new_instruction = st.text_area("New Instruction")
    if st.button("Add Instruction"):
        add_instruction(selected_db_id, new_instruction)

def update_instruction(instruction_id, new_instruction):
    url = f"{API_BASE_URL}/instructions/{instruction_id}"
    payload = {"instruction": new_instruction, "metadata": {}}
    response = requests.put(url, json=payload)
    if response.status_code == 200:
        st.success("Instruction updated successfully!")
        time.sleep(1)
        st.rerun()
    else:
        st.error(f"Failed to update instruction: {response.status_code}")

def delete_instruction(instruction_id):
    url = f"{API_BASE_URL}/instructions/{instruction_id}"
    response = requests.delete(url)
    if response.status_code == 200:
        st.success("Instruction deleted successfully!")
        time.sleep(1)
        st.rerun()
    else:
        st.error(f"Failed to delete instruction: {response.status_code}")

def add_instruction(db_connection_id, instruction):
    url = f"{API_BASE_URL}/instructions"
    payload = {"db_connection_id": db_connection_id, "instruction": instruction, "metadata": {}}
    response = requests.post(url, json=payload)
    if response.status_code in [200, 201]:
        st.success("Instruction added successfully!")
        time.sleep(1)
        st.rerun()
    else:
        st.error(f"Failed to add instruction: {response.status_code}")

def get_database_connections():
    response = requests.get(f"{API_BASE_URL}/database-connections")
    if response.status_code in [200, 201]:
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            st.error("Failed to parse database connections response")
            return []
    else:
        st.error(f"Failed to fetch database connections: {response.status_code}")
        return []

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
    if response.status_code in [200, 201]:
        print(f"SQL generation response: {response}")
        return response.json()
    else:
        st.error(f"Failed to generate SQL: {response.status_code}")
        return None

def get_generated_sql(sql_generation_id):
    url = f'{API_BASE_URL}/sql-generations/{sql_generation_id}'
    response = requests.get(url)
    if response.status_code in [200, 201]:
        return response.json()
    else:
        st.error(f'Failed to fetch generated SQL: {response.status_code}')
        return None

if __name__ == "__main__":
    main()
