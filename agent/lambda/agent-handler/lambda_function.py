import os
import json
import time
import boto3
import pdfrw
import difflib
import logging
import datetime
import dateutil.parser

from chat import Chat
from genai_agent import GenAIAgent
from boto3.dynamodb.conditions import Key
from langchain.llms.bedrock import Bedrock

# Create reference to DynamoDB tables and S3 bucket
loan_application_table_name = os.environ['USER_PENDING_ACCOUNTS_TABLE']
user_accounts_table_name = os.environ['USER_EXISTING_ACCOUNTS_TABLE']
s3_artifact_bucket = os.environ['S3_ARTIFACT_BUCKET_NAME']

# Instantiate boto3 clients and resources
boto3_session = boto3.Session(region_name=os.environ['AWS_REGION'])
dynamodb = boto3.resource('dynamodb', region_name=os.environ['AWS_REGION'])
s3_client = boto3.client('s3', region_name=os.environ['AWS_REGION'],
                         config=boto3.session.Config(signature_version='s3v4', ))
s3_object = boto3.resource('s3')
bedrock_client = boto3_session.client(service_name="bedrock-runtime")


# --- Lex v2 request/response helpers (https://docs.aws.amazon.com/lexv2/latest/dg/lambda-response-format.html) ---

def elicit_slot(session_attributes, active_contexts, intent, slot_to_elicit, message):
    """
    Constructs a response to elicit a specific Amazon Lex intent slot value from the user during conversation.
    """
    response = {
        'sessionState': {
            'activeContexts': [{
                'name': 'intentContext',
                'contextAttributes': active_contexts,
                'timeToLive': {
                    'timeToLiveInSeconds': 86400,
                    'turnsToLive': 20
                }
            }],
            'sessionAttributes': session_attributes,
            'dialogAction': {
                'type': 'ElicitSlot',
                'slotToElicit': slot_to_elicit
            },
            'intent': intent,
        },
        'messages': [{
            "contentType": "PlainText",
            "content": message,
        }]
    }

    return response


def elicit_intent(intent_request, session_attributes, message):
    """
    Constructs a response to elicit the user's intent during conversation.
    """
    response = {
        'sessionState': {
            'dialogAction': {
                'type': 'ElicitIntent'
            },
            'sessionAttributes': session_attributes
        },
        'messages': [
            {
                'contentType': 'PlainText',
                'content': message
            },
            # TODO: Remove this card or replace with new commands
            # UPDATE: changed command to FAQ questions
            {
                'contentType': 'ImageResponseCard',
                'imageResponseCard': {
                    "buttons": [
                        {
                            "text": "About Enviroflares",
                            "value": "What is Enviroflares?"
                        },
                        {
                            "text": "About this chatbot",
                            "value": "Who can I ask about this chatbot?"
                        },
                        {
                            "text": "Ask GenAI",
                            "value": "What kind of questions can you answer?"
                        }
                    ],
                    "title": "How can I help you?"
                }
            }
        ]
    }

    return response


def try_ex(value):
    """
    Safely access slots dictionary values.
    """
    if value is not None:
        if value['value']['resolvedValues']:
            return value['value']['interpretedValue']
        elif value['value']['originalValue']:
            return value['value']['originalValue']
        else:
            return None
    else:
        return None


def invoke_agent(user_prompt, event):
    """
    Invokes Amazon Bedrock-powered LangChain agent with 'prompt' input.
    """
    # Allocate message history resource to this chat whenever this function is called
    chat = Chat(event)
    # Basic model access and configuration
    llm = Bedrock(client=bedrock_client, model_id="anthropic.claude-3-haiku-20240307-v1:0",
                  region_name=os.environ['AWS_REGION'])  # Available: anthropic.claude-3-sonnet-20240229-v1:0
    # TODO: change this parameter `max_tokens_to_sample` to finetune
    llm.model_kwargs = {'max_tokens_to_sample': 350}

    # Define conversational agent with defined Bedrock LLM and chat memory
    this_agent = GenAIAgent(llm, chat.memory)
    agent_response = this_agent.run(user_prompt)

    return agent_response


def genai_intent(intent_request):
    """
    Performs dialog management and fulfillment for user utterances that do not match defined intents (e.g., FallbackIntent).
    Sends user utterance to the 'invoke_agent' method call.
    """
    # Get username to handle session distribution
    slots = intent_request['sessionState']['intent']['slots']
    username = try_ex(slots['UserName'])
    # Get the current session attributes
    session_attributes = intent_request['sessionState'].get("sessionAttributes") or {}
    # Assign UserName for the current session
    session_attributes['UserName'] = username

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Get user prompt
        user_prompt = intent_request['inputTranscript']
        # Invoke the GenAI agent with user prompt and event (session attributes)
        agent_response = invoke_agent(user_prompt, session_attributes)
        print("GenAI Agent response: " + str(agent_response))

    return elicit_intent(intent_request, session_attributes, agent_response)


# --- Intents ---

def dispatch(intent_request):
    """
    Routes the incoming request based on intent.
    """
    return genai_intent(intent_request)


# --- Main handler ---

def handler(event, context):
    """
    Invoked when the user provides an utterance that maps to a Lex bot intent.
    The JSON body of the user request is provided in the event slot.
    """
    os.environ['TZ'] = 'Australia/Sydney'
    time.tzset()

    return dispatch(event)
