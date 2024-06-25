from boto3.dynamodb.types import TypeSerializer
from langchain.memory.chat_message_histories import DynamoDBChatMessageHistory
from langchain.memory import ConversationBufferMemory
from datetime import datetime
import json
import boto3
import os

now = datetime.utcnow() # Get current time in UTC
dynamodb = boto3.client('dynamodb')
ts = TypeSerializer()

# Create reference to DynamoDB tables
conversation_index_table_name = os.environ.get('CONVERSATION_INDEX_TABLE') # save conversation index
conversation_table_name = os.environ.get('CONVERSATION_TABLE') # save conversation memory


class Chat:
    """
    Chat class that handles the conversation history and memory for the AI agent.
    Each new conversation is created and stored with a new chat_index = old chat_index + 1.
    Each user uses the chatbot has a user_id (currently hardcoded as "Demo User").
    --> A conversation is saved with conversation_id = user_id + '-' + chat_index.
    """

    def __init__(self, event):
        self.chat_index = None
        self.user_id = None
        self.message_history = None
        self.memory = None
        print("Initializing Chat with GenAI Agent")
        # Set up the chat memory:
        self.set_user_id(event)
        self.set_chat_index() # Chat index by user (user_id)
        self.set_memory(event) # Conversation memory by user_id and chat_index of that user
        self.create_new_chat()

    def set_memory(self, event):
        # Create conversation id = combine user_id and chat_index of that user
        conversation_id = self.user_id + "-" + str(self.chat_index)

        # Set up conversation history and store current event
        self.message_history = DynamoDBChatMessageHistory(table_name=conversation_table_name,
                                                          session_id=conversation_id)
        # TODO: Double check if event = session_attributes or event = intent_request[...] -> hints from later parts
        # TODO: research `event` should contain what?
        self.message_history.add_user_message(event)

        # Set up conversation memory
        self.memory = ConversationBufferMemory(
            ai_prefix="Assistant",
            memory_key="chat_history",
            chat_memory=self.message_history,
            input_key="input",
            output_key="output",
            return_messages=True
        )

    def get_chat_index(self):
        """
        Get the chat index for the current user - checking the conversation index table with key=user_id
        :return: chat index if this user has previous conversation, else 0
        """
        key = {'id': self.user_id}
        chat_index = dynamodb.get_item(TableName=conversation_index_table_name, Key=ts.serialize(key)['M'])
        if 'Item' in chat_index:
            return int(chat_index['Item']['chat_index']['N'])
        return 0

    def increment_chat_index(self):
        self.chat_index += 1
        # Current user uses chat_index + 1; next user will use chat_index + 1 + 1; previous user used chat_index
        conversation_log = {
            'id': self.user_id,
            'chat_index': self.chat_index,
            'updated_at': str(now)
        }
        dynamodb.put_item(TableName=conversation_index_table_name, Item=ts.serialize(conversation_log)['M'])

    def create_new_chat(self):
        self.increment_chat_index()

    def set_user_id(self, event):
        # TODO: Get user id from the parsed in parameters (e.g: event) (DONE)
        # original: self.user_id = "Demo User" (hardcoded)
        # updated: user_id is the UserName from the current session attributes
        self.user_id = event['UserName']

    def set_chat_index(self):
        self.chat_index = self.get_chat_index()
