## What it does
Our project was developed to help people recycle, upcycle, and resell objects that would otherwise have gone to landfills and polluted the environment.
It is an app that lets you upload an image or take a picture of an object, which is processed by an LLM, Qwen3.5:4b, in order to generate DIY project ideas that the user
can make to upcycle the trash into something creative and useful. If the item is e-waste or hazardous waste that needs to be disposed of at a dropoff site, our tool tells the user where the closest dropoff site is based on the user's zipcode, which the user needs to input, using the Google Maps API. We also wanted to educate the user on facts and best practices about recycling and waste management so we added a list of fun facts that cycle on the screen when the local LLM anaylzes the images and synthesizes the output. We also added a small quiz that the user can do to test and grow their knowledge about recycling and waste management.

## How we built it
We used Python to code the entire project and we used Ollama to locally run the LLMs as it makes extracting structured output from the LLM easy. Pydantic was also used to extract and validate the structured output from Qwen3.5:4b.

## Accomplishments that we're proud of
We integrated Google Maps API into the project. This made our project more practical because it gives the user information about where the nearest dropoff or donation center is, saving them an extra search. This reduces the friction that is associated with recycling as it easier for the user as all they need to do is take a picture of their trash and the app will tell them where to take it to dispose of, or to donate it.
