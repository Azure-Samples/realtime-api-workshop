# Advanced Exercises

## Prompt Engineering

In this part of the workshop, we will enhance the prompt for the VoiceRAG model. The default prompt is simple, and we can significantly improve the grounding and behavior by adding more context here. Additionally, you can also adjust the voice to better reflect your brand by modifying the prompt.

Grounding ensures that the model's responses are relevant and accurate based on the provided context. Here are some tips to improve grounding:
1. **Provide Clear Instructions**: Clearly state the task or question you want the model to address.
2. **Include Relevant Context**: Add any necessary background information or context that the model needs to generate a more accurate response.
3. **Specify the Desired Format**: If you need the response in a specific format, make sure to include this in the prompt.

You can also adjust the tone and style of the responses by tweaking the prompt. This can help align the model's output with your brand's voice. Here are some tips:

1. **Define the Tone**: Specify whether the tone should be formal, casual, friendly, professional, etc.
2. **Use Example Phrases**: Provide example phrases or sentences that reflect the desired tone.
3. **Adjust for Specific Scenarios**: Tailor the prompt for different scenarios to ensure the model responds appropriately in various contexts.

> [!TIP]
> You can modify the prompt (also known as system message) in the `app/backend/app.py` file. Modify the `rtmt.system_message`.

### Exercise 1

1. Change the voice and style to better reflect your use-case. You can change the voice by configuring the `AZURE_OPENAI_REALTIME_VOICE_CHOICE` environment variable. Current voice options are `alloy`, `ash`, `ballad`, `coral`, `echo`, `sage`, `shimmer` and `verse`. Can you make the voice style more formal and professional, you are building a voice first experience for a corporate use-case.

   Which voice do you like the most?

2. Modify the prompt to reply in easier language to your end users. Can your VoiceRAG solution explain the difficult concepts in a simpler way? Since you are building a voice first experience, can you make the answers more conversational and concise?

3. Modify the prompt to always reply to the user in your language of choice. 

## Modify the interface

The text in this accelerator is translateable and can be modified by navigating to `/app/frontend/locales/en/translations.json`. Make sure to run to restart the application after making changes. 

Navigate to `/app/frontend/src/App.tsx` to modify the interface and/or logic in code, knowledge of front-end development and React is required.

### Exercise 2

1. Change the text "Ask anything about Contoso employee benefits" to "Ask anything about [your company's] [use-case]".

## Function calling

This accelerator uses two tools to generate responses. The first tool generates a query to search the knowledge base. The second tool reports which sources were used to generate the response.

The purpose of this setup is to ensure that the interface displays the grounding of the response, and to make sure the voice response doesn't mention all output sources.

> [!TIP]
> You can modify the tools (functions) in the `app/backend/ragtools.py` file. Modify the description of the tool and/or parameters.
> 
### Exercise 3

1. Review the tool schema for both tools. Can you add more information to the query generation tool to make it more accurate for your use-case?


