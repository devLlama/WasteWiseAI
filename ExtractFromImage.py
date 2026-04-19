import os
from typing import List, Optional
import googlemaps
from ollama import chat
from pydantic import BaseModel, Field
from enum import StrEnum, auto
from dotenv import load_dotenv
import time

#Model name is referenced in multiple classes so it is a global variable.
global MODEL_NAME
#qwen3.5:4b gave the best time while having the best quality.
MODEL_NAME = "qwen3.5:4b"

load_dotenv()
google_maps_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

class Disposability(StrEnum):
    GENERAL_TRASH = auto(),
    HAZARDOUS_WASTE = auto(),
    ORGANIC_WASTE = auto(),
    ELECTRONIC_WASTE = auto(),
    RECYCLABLE = auto(),

class Sellability(StrEnum):
    SELLABLE = auto(),
    NOT_SELLABLE = auto(),

class ProjectUsability(StrEnum):
    USABLE_FOR_A_PROJECT = auto(),
    NOT_USABLE_FOR_A_PROJECT = auto(),

class Item(BaseModel):
    item_name: str
    size: str
    description: str
    disposability: Disposability = Field(description="What type of trash is this? Anything related to electronics is electronic waste. Batteries are electronic waste.")
    sellabity: Sellability = Field(description="In the condition the item is in, could it be sold?")
    project_usability: ProjectUsability = Field(description="Could this item be used effectively in a DIY Project?")

class ItemList(BaseModel):
    items: List[Item]

class ExtractFromImage:
    # MODEL_NAME = "qwen3.5:0.8b"
    prompt = "Tell me about the main items in the image. This will be used to give the user recommendations about recycling or upcylcing the item. The item name is a general name for the thing in the image. The size is whether it is a full version of the item or a scrap or a part of it. Things like batteries are electronic waste and cannot be recycled they must be classified as electronic_waste regardless of if the image says the battery is recyclable. An item is useable for a project if it has materials that can be used for a craft project or some similar DIY project."  # make better prompt

    @classmethod
    def extract(cls, image_paths:List[str]):
        response = chat(
            # model=cls.MODEL_NAME,
            model=MODEL_NAME,
            messages=[
                {
                    "role" : "user",
                    "content" : cls.prompt,
                    "images" : image_paths,
                }
            ],
            options={
                'seed': 42,
                "temperature": 0,
            },
            format=ItemList.model_json_schema(),
        )
        output = ItemList.model_validate_json(response.message.content)
        return output

class ItemParse:
    # MODEL_NAME = "qwen3.5:0.8b"

    @classmethod
    def get_place_details(cls, place_id: str) -> dict:
        gmaps = googlemaps.Client(key=google_maps_api_key)
        details = gmaps.place(
            place_id=place_id,
            fields=['name', 'formatted_address', 'opening_hours']
        )
        result = details.get('result', {})
        return {
            "name": result.get('name'),
            "address": result.get('formatted_address'),
            "hours": result.get('opening_hours', {}).get('weekday_text', []),
            "open_now": result.get('opening_hours', {}).get('open_now'),
            "maps_link": f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        }

    #keyword for e-waste: electronics recycling e-waste drop off
    #keyword for toxic waste: hazardous waste disposal toxic waste drop off
    #keyword for charity: donation center charity thrift store goodwill salvation army
    @classmethod
    def get_closest_location(cls, zipcode, keyword):
        gmaps = googlemaps.Client(key=google_maps_api_key)
        geocode_result = gmaps.geocode(zipcode)
        if geocode_result is not None:
            location = geocode_result[0]['geometry']['location']
            places_result = gmaps.places_nearby(
                location=location,
                keyword=keyword,
                rank_by='distance',
                type='point_of_interest'
            )
            closest = places_result['results'][0]
            return cls.get_place_details(closest['place_id'])

    @classmethod
    def parse_item(cls, item: Item, zipcode):
        disposing_maps_link = None
        selling_maps_link = None

        if item.disposability == Disposability.GENERAL_TRASH:
            item_disposing_options = "This item can be placed in a normal trash bin."

        elif item.disposability == Disposability.HAZARDOUS_WASTE:
            location = cls.get_closest_location(zipcode,
                                                "hazardous waste disposal toxic waste drop off") if zipcode else None
            if location:
                disposing_maps_link = location['maps_link']
                item_disposing_options = (
                    f"This item must be taken to a hazardous waste collection center. "
                    f"The closest is **{location['name']}** at {location['address']} "
                    f"({'open now' if location['open_now'] else 'currently closed'}). "
                    f"Hours: {', '.join(location['hours'])}."
                )
            else:
                item_disposing_options = "This item must be taken to a hazardous waste collection center."

        elif item.disposability == Disposability.ORGANIC_WASTE:
            item_disposing_options = "This item can be placed in a green waste bin or a normal trash bin."

        elif item.disposability == Disposability.ELECTRONIC_WASTE:
            location = cls.get_closest_location(zipcode, "electronics recycling e-waste drop off") if zipcode else None
            if location:
                disposing_maps_link = location['maps_link']
                item_disposing_options = (
                    f"This item must be taken to an electronic waste collection center. "
                    f"The closest is **{location['name']}** at {location['address']} "
                    f"({'open now' if location['open_now'] else 'currently closed'}). "
                    f"Hours: {', '.join(location['hours'])}."
                )
            else:
                item_disposing_options = "This item must be taken to an electronic waste collection center."

        elif item.disposability == Disposability.RECYCLABLE:
            item_disposing_options = "This item can be placed in a recycling bin."

        else:
            item_disposing_options = "This item cannot be disposed of safely."

        if item.sellabity == Sellability.SELLABLE:
            charity = cls.get_closest_location(zipcode,
                                               "donation center charity thrift store goodwill salvation army") if zipcode else None
            if charity:
                selling_maps_link = charity['maps_link']
                item_selling_options = (
                    f"This item could be sold on Facebook Marketplace, or donated locally. "
                    f"The closest donation center is **{charity['name']}** at {charity['address']} "
                    f"({'open now' if charity['open_now'] else 'currently closed'}). "
                    f"Hours: {', '.join(charity['hours'])}."
                )
            else:
                item_selling_options = "This item could be sold on Facebook Marketplace, or donated to a local charity."
        else:
            item_selling_options = "This item is not suitable for selling or donating."

        if item.project_usability == ProjectUsability.USABLE_FOR_A_PROJECT:
            prompt = (
                f"{item.item_name} + {item.size} + {item.description} "
                f"Come up with 5 useful, practical, DIY project ideas that could be made with this item. "
                f"Include a title for the project idea, the needed materials to make it, and the steps the user must take to make it. "
                f"Make the first 2 ideas easy to make, the 3rd and 4th ideas medium in difficulty and the last idea the hardest to make. "
                f"Make the projects as practical and as useful as possible. Make the projects use common household items to make."
            )
            response = chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                options={"seed": 42, "temperature": 0},
                think=False,
            )
            item_using_options = response.message.content
        else:
            item_using_options = "This item is not suitable for any DIY project."

        return {
            "item": item,
            "item_disposing_options": item_disposing_options,
            "item_selling_options": item_selling_options,
            "item_using_options": item_using_options,
            "disposing_maps_link": disposing_maps_link,
            "selling_maps_link": selling_maps_link,
        }