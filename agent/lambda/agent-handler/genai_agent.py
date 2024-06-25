from langchain.agents.tools import Tool
from langchain.agents.conversational.base import ConversationalAgent
from langchain.agents import AgentExecutor
from tools import Tools
from datetime import datetime


class GenAIAgent:
    """
    Create an AI agent that can be used to answer questions or perform tasks using a set of predefined tools.
    tools_instance.kendra_search is a custom tool that the agent can use to retrieve information.
    """

    def __init__(self, llm, memory) -> None:
        # Set up GenAI Agent
        # Call the genai agent "Assistant"
        self.ai_prefix = "Assistant"
        # Call the user of chatbot "Human"
        self.human_prefix = "Human"
        # Parsed in LLM and memory
        self.llm = llm
        self.memory = memory
        # RAG tool using Kendra search and indexing
        self.tools_instance = Tools()
        # Create the agent
        self.agent = self.create_agent()

    def create_agent(self):

        # Initialize the agent RAG tool using Kendra defined in tools.py
        RAG_Kendra_tool = Tool(name="RAG with Amazon Kendra", func=self.tools_instance.kendra_search,
                               description="Use this tool to provide responses using information from your documents.")

        genai_agent = ConversationalAgent.from_llm_and_tools(
            llm=self.llm,
            tools=[RAG_Kendra_tool],
            ai_prefix=self.ai_prefix,
            human_prefix=self.human_prefix,
            verbose=True,
            return_intermediate_steps=True,
            return_source_documents=True
        )

        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=genai_agent,
            tools=[RAG_Kendra_tool],
            verbose=True,
            memory=self.memory,
            return_source_documents=True,
            return_intermediate_steps=True
        )

        return agent_executor

    def run(self, user_prompt):
        print("Running GenAI Agent with input: " + str(user_prompt))
        try:
            # Parse the user prompt to perform RAG and generate a response
            response = self.tools_instance.kendra_search(user_prompt)
        except ValueError as e:
            print(f"Error running agent: {e}")
            response = "Sorry! It appears we have encountered an issue."

        return response
