import os
import json
import boto3
from langchain.agents.tools import Tool

bedrock = boto3.client('bedrock-runtime', region_name=os.environ['AWS_REGION'])


class Tools:
    """
    This class provides a Kendra search tool that can be used to answer questions by querying an Amazon Kendra index.
    """

    def __init__(self) -> None:
        print("Initializing Tools")
        self.tools = [
            Tool(
                name="RAG_Kendra_tool",
                func=self.kendra_search,
                description="Use this tool to provide responses using information from your documents.",
            )
        ]

    def parse_kendra_response(self, kendra_response):
        """
        Extracts the source URI from document attributes in Kendra response.
        """
        modified_response = kendra_response.copy()
        result_items = modified_response.get('ResultItems', [])

        for item in result_items:
            source_uri = None
            if item.get('DocumentAttributes'):
                for attribute in item['DocumentAttributes']:
                    if attribute.get('Key') == '_source_uri':
                        source_uri = attribute.get('Value', {}).get('StringValue', '')

            if source_uri:
                print(f"Amazon Kendra Source URI: {source_uri}")
                item['_source_uri'] = source_uri

    def kendra_search(self, user_prompt):
        """
        Performs a Kendra search using the Query API.
        """
        kendra = boto3.client('kendra')

        kendra_search_result = kendra.query(
            IndexId=os.getenv('KENDRA_INDEX_ID'),
            QueryText=user_prompt,
            PageNumber=1, # Get the first page of result
            PageSize=5  # Limit to 5 results per response page
        )

        # Print Kendra source URI
        self.parse_kendra_response(kendra_search_result)
        # Print query result
        print(f"Amazon Kendra Query Item: {kendra_search_result}")

        # passing in the original question, and various Kendra responses as context into the LLM
        return self.invokeLLM(user_prompt, kendra_search_result)

    def invokeLLM(self, user_prompt, context):
        """
        Generates an answer for the user using RAG with context from Kendra response.
        """
        # Enrich the prompt with context before passing it to the LLM
        # TODO: CHANGE THE SYSTEM PROMPT (DONE)
        prompt_data = f"""
        Human:
        Act as an internal chatbot assistant for a company named Enviroflares.
        Your role is to provide accurate and relevant information in response to specific questions from employees by checking your knowledge base from uploaded documents and using your general knowledge as a pre-trained Large Language Model. 

        Here are some important guidelines for the interaction:
        - Whenever a user asks a question, first refer to the provided context from the uploaded documents.
        - If the answer can be found in the uploaded documents, provide the information directly from there.
        - If the information is not available in the context, use your general knowledge to answer the question.
        - If user's question is unclear or lacks sufficient information for a response, please seek further information from the user.
        - Always ensure the information is up-to-date and accurate. Cite the sources of information you use for your answer only, not all available sources.
        - Respond quickly and in a friendly manner.
        - Format your response for enhanced human readability.

        Using the following context, answer the following question to the best of your ability. Do not include information that is not relevant to the question, and only provide information based on the context provided without making assumptions. 

        Question: {user_prompt}

        Context: {context}

        \n\nAssistant:
        """

        # Formatting the prompt as JSON
        # TODO: change some attributes of the json prompt to finetune
        json_prompt = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 3500,
            "temperature": 0.4,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_data
                        }
                    ]
                }
            ]
        })

        # Invoking Claude3, passing in our JSON prompt
        response = bedrock.invoke_model(
            body=json_prompt,
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            accept="application/json",
            contentType="application/json"
        )

        # Getting the response from Claude3 and parsing it to return to the end user
        response_body = json.loads(response['body'].read())
        answer = response_body['content'][0]['text']

        return answer


# Pass the initialized retriever and llm to the Tools class constructor
tools = Tools().tools
