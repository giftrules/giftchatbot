from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from word2number import w2n
import yaml
import difflib
import re

from rasa.shared.core.events import UserUttered
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import (
    SessionStarted,
    ActionExecuted,
    SlotSet,
    EventType,
    UserUtteranceReverted,
)
import requests
import logging
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher
import os


API_BASE_URL = "http://localhost:1200"  # Your Flask backend URL
DEFAULT_CUSTOMER_ID = 0  # fallback customer ID
DEFAULT_USERTYPE = 2  # fallback usertype
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Shared helper: ask for a missing slot and revert last user message
# ------------------------------------------------------------------
# Initialize lists to hold examples with no entities
stock_keywords = []
price_keywords = []

def load_generic_examples():
    global stock_keywords, price_keywords
    with open("data/nlu.yml", "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    for item in data.get("nlu", []):
        intent = item.get("intent")
        examples = item.get("examples", "")

        for ex in examples.strip().split("\n"):
            ex = ex.strip("- ").strip()

            # If no entity annotation like [xxx](product_name), save it
            if not re.search(r"\[.*?\]\(.*?\)", ex):
                if intent == "check_stock":
                    stock_keywords.append(ex.lower())
                elif intent == "find_product_price":
                    price_keywords.append(ex.lower())
def ask_for_slot(
    dispatcher: CollectingDispatcher, slot_name: str, question: str
) -> List[EventType]:
    dispatcher.utter_message(text=question)
    return [UserUtteranceReverted(), SlotSet(slot_name, None)]

class DisplayConfidenceLevel(Action):
    def name(self) -> Text:
        return "display_confidence_level"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:

        user_msg = tracker.latest_message.get("text")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        entities = tracker.latest_message.get("entities")

        # Log or print to console
        print(f"User Message: {user_msg}")
        print(f"Matched Intent: {intent} | Confidence: {confidence}")
        print(f"Entities: {entities}")

        print(f"[DEBUG] Intent: {intent} | Confidence: {confidence:.2f}")

        # Optionally message the user or set a slot
        if confidence < 0.6:
            dispatcher.utter_message(text="Hmm, I'm not too confident I understood.")
        else:
            dispatcher.utter_message(text="--------------------")

        return []
# ------------------------------------------------------------------
# Read all FAQ
# ------------------------------------------------------------------
class ActionShowAllFaqs(Action):
    def name(self):
        return "action_show_all_faqs"

    def run(self, dispatcher, tracker, domain):
        faq_file = "data/nlu.yml"  # Adjust path if needed
        logger.info("Starting action_show_all_faqs")
        if not os.path.exists(faq_file):
            dispatcher.utter_message("⚠️ FAQ data file not found.")
            return []

        with open(faq_file, 'r', encoding='utf-8') as file:
            content = yaml.safe_load(file)

        grouped_faqs = {}
        #logger.info(content)
        for entry in content.get("nlu", []):
            #logger.info(entry)
            if isinstance(entry, dict) and "intent" in entry and entry["intent"].startswith("faq/"):
                category = entry["intent"].split("/")[1].replace("_", " ").title()
                examples_text = entry.get("examples", "")
                questions = [line.strip("- ").strip() for line in examples_text.strip().splitlines() if line.strip()]
                if questions:
                    grouped_faqs[category] = questions[0]  # Only take the first example

        if not grouped_faqs:
            dispatcher.utter_message("No FAQ data found.")
            return []

        final_message = ""
        emoji_map = {
            "Shipping": "📦",
            "Returns": "🔄",
            "Delivery Time": "⏱️",
            "How To Order": "🛒",
            "Payment Methods": "💳",
            "Account Help": "👤",
            "Contact Support": "📞",
            "Order Changes": "✏️",
            "Warranty Info": "🛡️"
        }

        for category, question in grouped_faqs.items():
            emoji = emoji_map.get(category, "❓")
            final_message += f"\n\n{emoji} *{category.upper()}*\n- {question}"
        logger.info(final_message)
        dispatcher.utter_message(text=final_message.strip())
        return []
# ------------------------------------------------------------------
# 0) Session Start Action
# ------------------------------------------------------------------
class ActionSessionStart(Action):
    def name(self) -> Text:
        return "action_session_start"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_session_start")
        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)
        usertype = metadata.get("usertype", None)
        events = [SessionStarted()]

        try:
            resp = requests.get(f"{API_BASE_URL}/customers/{customer_id}")
            if resp.status_code == 200:
                name = resp.json().get("name", "there")
                dispatcher.utter_message(text=f"Hello {name}, how can I help you today?")
            else:
                dispatcher.utter_message(text="Hello, how can I assist you today?")
        except Exception:
            dispatcher.utter_message(text="Welcome! How can I assist you today?")

        # Set customer_id slot explicitly after session start reset
        events.append(SlotSet("customer_id", customer_id))
        events.append(ActionExecuted("action_listen"))
        return events



# ------------------------------------------------------------------
# 2) Check Stock
# ------------------------------------------------------------------
class ActionCheckStock(Action):
    def name(self) -> Text:
        return "action_check_stock"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        logger.info("Starting action_check_stock")

        user_msg = tracker.latest_message.get("text")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        entities = tracker.latest_message.get("entities")

        # Log or print to console
        print(f"User Message: {user_msg}")
        print(f"Matched Intent: {intent} | Confidence: {confidence}")
        print(f"Entities: {entities}")

        print(f"[DEBUG] Intent: {intent} | Confidence: {confidence:.2f}")
        product_name = tracker.get_slot("product_name")
        load_generic_examples()
        if tracker.latest_message.get("text", "").lower() in stock_keywords :
            product_name="everything"
        elif not product_name and not entities:
            return ask_for_slot(
                dispatcher,
                "product_name",
                "Which product would you like to check stock for?"
            )

        try:
            resp = requests.get(f"{API_BASE_URL}/products", params={"name": product_name})
            if resp.status_code == 200:
                products = resp.json()
                if not products:

                    dispatcher.utter_message(text=f"I couldn't find {product_name}. We dont have it in stock at the moment")
                else:
                    messages = []
                    for p in products:
                        product_id = p.get("id", "N/A")
                        name = p.get("name", "Unknown product")
                        category = p.get("category", "Unknown category")
                        stock = p.get("stock", 0)
                        price = p.get("price", 0.00)
                        price_formatted = f"{price:.2f}"
                        messages.append(
                            f"Category: {category}\nProduct ID: {product_id}\nName: {name}\nStock: {stock}\nPrice: ${price_formatted}"
                        )
                    final_message = "\n\n-----------------------------\n\n".join(messages)
                    dispatcher.utter_message(text=f"Here are the matching products:\n\n---------------------------------------------\n{final_message}")
                    return [SlotSet("product_name", None)]
            else:
                dispatcher.utter_message(text=f"Sorry, I couldn't check the stock of {product_name} at the moment.\n\nPlease note that we only sell electronics!")
        except Exception as e:
            dispatcher.utter_message(text="Something went wrong while checking the stock.")
            print("Error in action_check_stock:", e)

        return []
# ------------------------------------------------------------------
# 3) Add to Cart
# ------------------------------------------------------------------
class ActionAddToCart(Action):
    def name(self) -> Text:
        return "action_add_to_cart"

    def run(
            self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_add_to_cart")
        user_msg = tracker.latest_message.get("text")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        entities = tracker.latest_message.get("entities")

        # Log or print to console
        print(f"User Message: {user_msg}")
        print(f"Matched Intent: {intent} | Confidence: {confidence}")
        print(f"Entities: {entities}")

        print(f"[DEBUG] Intent: {intent} | Confidence: {confidence:.2f}")
        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)
        usertype = metadata.get("usertype", None)
        product_name = tracker.get_slot("product_name")
        quantity = tracker.get_slot("quantity") or 1

        if not product_name  and not entities:
            return ask_for_slot(
                dispatcher, "product_name", "Which product would you like to add to your cart?"
            )

        # Convert quantity from text to int
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            try:
                quantity = w2n.word_to_num(quantity)
            except Exception:
                quantity = 1  # fallback if conversion fails

        payload = {
            "customer_id": customer_id,
            "product_name": product_name,
            "quantity": quantity,
        }
        resp = requests.post(f"{API_BASE_URL}/cart_items", json=payload)
        if resp.status_code == 201:
            dispatcher.utter_message(
                text=f"Added {quantity} × {product_name} to your cart."
            )
        else:
            dispatcher.utter_message(text=f"Sorry, I couldn't add '{product_name}' to your cart.")
        return []

# ------------------------------------------------------------------
# 4) Find Product Price
# ------------------------------------------------------------------
class ActionFindProductPrice(Action):
    def name(self) -> Text:
        return "action_find_product_price"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        logger.info("Starting action_find_product_price")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        print(f"[Fallback Triggered] Intent detected: {intent}, confidence: {confidence}")
        product_name = tracker.get_slot("product_name")
        entities = tracker.latest_message.get("entities")
        load_generic_examples()
        if tracker.latest_message.get("text", "").lower() in price_keywords :
            product_name="everything"
        elif not product_name and not entities:
            return ask_for_slot(
                dispatcher,
                "product_name",
                "Which product's price would you like to know?"
            )

        try:
            resp = requests.get(f"{API_BASE_URL}/products", params={"name": product_name})
            if resp.status_code == 200:
                products = resp.json()
                if not products:
                    dispatcher.utter_message(text=f"I couldn't find that product named '{product_name}'.")
                else:
                    messages = []
                    for p in products:
                        product_id = p.get("id", "N/A")
                        name = p.get("name", "Unknown")
                        price = p.get("price", 0.00)
                        price_formatted = f"{price:.2f}"
                        messages.append(
                            f"Product ID: {product_id}\nName: {name}\nPrice: ${price_formatted}"
                        )
                    final_message = "\n\n---------------------\n\n".join(messages)
                    dispatcher.utter_message(text=f"Here are the matching products:\n\n---------prices-----------------\n\n{final_message}")
            else:
                dispatcher.utter_message(text=f"Sorry, I couldn't fetch product prices for '{product_name}' right now.\n We only sell electronics")
        except Exception as e:
            dispatcher.utter_message(text="An error occurred while fetching the product price.")
            print("Error in action_find_product_price:", e)

        return []
# ------------------------------------------------------------------
# 5) Find Cart Total
# ------------------------------------------------------------------
class ActionFindCartTotal(Action):
    def name(self) -> Text:
        return "action_find_cart_total"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_find_cart_total")

        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)

        try:
            resp = requests.get(f"{API_BASE_URL}/cart_items/{customer_id}")

            if resp.status_code == 200:
                items = resp.json()
                if not items:
                    dispatcher.utter_message(text="Your cart is empty.")
                    return []

                total = 0.0
                item_lines = []
                for item in items:
                    name = item.get("product_name", "Unknown")
                    quantity = item.get("quantity", 0)
                    price = item.get("unit_price", 0.0)
                    subtotal = quantity * price
                    total += subtotal
                    item_lines.append(f"{name} (x{quantity}) - ${price:.2f} each")

                items_text = "\n".join(item_lines)
                dispatcher.utter_message(
                    text=f"Here are the products in your cart:\n\n{items_text}\n\nCart Total: ${total:.2f}"
                )
            else:
                dispatcher.utter_message(text="Sorry, I couldn't retrieve your cart.\nYour cart is empty.")
        except Exception as e:
            dispatcher.utter_message(text="An error occurred while checking your cart.")
            print("Error:", e)

        return []
# ------------------------------------------------------------------
# 6) Add Order
# ------------------------------------------------------------------
class ActionAddOrder(Action):
    def name(self) -> Text:
        return "action_add_order"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_add_order")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        print(f"[Fallback Triggered] Intent detected: {intent}, confidence: {confidence}")
        # Get customer metadata
        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)
        usertype = metadata.get("usertype", None)

        # Get items from cart
        try:
            cart_resp = requests.get(f"{API_BASE_URL}/cart_items/{customer_id}")
            if cart_resp.status_code != 200 or not cart_resp.json():
                dispatcher.utter_message(text="Your cart is empty or unavailable.\nMake sure you have items added to your cart.")
                return []

            cart_items = cart_resp.json()
            print(f"Cart items fetched for customer {customer_id}: {cart_items}")
        except Exception as e:
            dispatcher.utter_message(text=f"Error accessing your cart: {e}")
            return []

        # Prepare order payload
        order_payload = {
            "customer_id": customer_id,
            "items": cart_items
        }

        # Create order
        try:
            resp = requests.post(f"{API_BASE_URL}/orders", json=order_payload)
            if resp.status_code == 201:
                data = resp.json()
                dispatcher.utter_message(
                    text=(
                        f"✅ Your order has been placed successfully!\n"
                        f"🧾 Order ID: {data['order_id']}\n"
                        f"💰 Total: ${data['total_amount']:.2f}"
                    )
                )

            else:
                print(f"Order placement failed with status: {resp.status_code}, Response: {resp.text}")
                dispatcher.utter_message(text="❌ Failed to place the order. Please try again.")
        except Exception as e:
            print(f"Exception occurred while placing order: {e}")
            dispatcher.utter_message(text=f"❗ Error occurred while placing the order: {e}")

        return []

# ------------------------------------------------------------------
# 7) Update Order
# ------------------------------------------------------------------
class ActionUpdateOrder(Action):
    def name(self) -> Text:
        return "action_update_order"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker,    domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_update_order")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        print(f"[Fallback Triggered] Intent detected: {intent}, confidence: {confidence}")
        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)
        usertype = metadata.get("usertype", None)
        order_id = tracker.get_slot("order_id")

        if usertype != 1:
            dispatcher.utter_message(text="You are not authorized to do that.")
            return []
        entities = tracker.latest_message.get("entities")
        if not order_id and not entities:
            return ask_for_slot(dispatcher, "order_id", "What's the order ID you want to update?")

        payload = {"status": "Updated"}
        resp = requests.put(f"{API_BASE_URL}/orders/{order_id}", json=payload)
        if resp.status_code == 200:
            dispatcher.utter_message(text="Your order has been updated.")
        else:
            dispatcher.utter_message(text="Could not update the order.")
        return []


# ------------------------------------------------------------------
# 8) Delete Order
# ------------------------------------------------------------------
class ActionDeleteOrder(Action):
    def name(self) -> Text:
        return "action_delete_order"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker,    domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_delete_order")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        print(f"[Fallback Triggered] Intent detected: {intent}, confidence: {confidence}")
        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)
        usertype = metadata.get("usertype", 2)
        order_id = tracker.get_slot("order_id")
        entities = tracker.latest_message.get("entities")
        if usertype != 1:
            dispatcher.utter_message(text="You are not authorized to do that.")
            return []

        if not order_id or not entities:
            return ask_for_slot(dispatcher, "order_id", "Please provide the order ID you want to delete.")

        resp = requests.delete(f"{API_BASE_URL}/orders/{order_id}")
        if resp.status_code == 200:
            dispatcher.utter_message(text="Order deleted successfully.")
        else:
            dispatcher.utter_message(text="Unable to delete order.")
        return []


# ------------------------------------------------------------------
# 9) Check Order Status
# ------------------------------------------------------------------
class ActionCheckOrderStatus(Action):
    def name(self) -> Text:
        return "action_check_order_status"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker,  domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_check_order_status")
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        print(f"[Fallback Triggered] Intent detected: {intent}, confidence: {confidence}")
        metadata = tracker.latest_message.get("metadata", {})
        customer_id =int( metadata.get("customer_id", DEFAULT_CUSTOMER_ID))
        usertype =int( metadata.get("usertype", 2))
        order_id = tracker.get_slot("order_id")
        entities = tracker.latest_message.get("entities")
        if not order_id and not entities:
            return ask_for_slot(dispatcher, "order_id", "May I have the order ID to check its status?")

        resp = requests.get(f"{API_BASE_URL}/orders/{order_id}")
        if resp.status_code == 200 and resp.json():
            order = resp.json()
            logger.info(order['status'])
            if customer_id == order["customer_id"] or usertype==1:
                dispatcher.utter_message(
                    text=(
                        f"Order {order_id} is currently *{order['status']}* and totals ${order['total']:.2f}."
                    )
                )
            else :
                dispatcher.utter_message(
                    text=(
                        f"The Order you are searching for does not belong to you."
                    )
                )
        else:
            dispatcher.utter_message(text="I couldn't find that order.")
        return []


# ------------------------------------------------------------------
# 10) Ask Feedback / Collect Feedback
# ------------------------------------------------------------------
class ActionAskFeedback(Action):
    def name(self) -> Text:
        return "action_ask_feedback"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        logger.info("Starting action_ask_feedback")
        dispatcher.utter_message(text="Before you go, do you have any feedback for us?")
        return []


class ActionCollectFeedback(Action):
    def name(self) -> Text:
        return "action_collect_feedback"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker ,  domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        logger.info("Starting action_collect_feedback")
        metadata = tracker.latest_message.get("metadata", {})
        customer_id = metadata.get("customer_id", DEFAULT_CUSTOMER_ID)
        usertype = metadata.get("usertype", None)
        feedback = tracker.get_slot("feedback_text")
        payload = {"customer_id": customer_id, "comment": feedback}
        resp = requests.post(f"{API_BASE_URL}/chatbotreviews", json=payload)
        if resp.status_code == 201:
            dispatcher.utter_message(text="Thanks for your feedback!")
        else:
            dispatcher.utter_message(text="Could not save your feedback.")
        return []

class ActionDefaultFallback(Action):
    def name(self) -> Text:
        return "action_default_fallback"

    def run(self, dispatcher: CollectingDispatcher, tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Log fallback trigger info
        intent = tracker.latest_message.get("intent", {}).get("name")
        confidence = tracker.latest_message.get("intent", {}).get("confidence")
        print(f"[Fallback Triggered] Intent: {intent}, Confidence: {confidence}")

        # Load training examples
        with open("data/nlu.yml", "r", encoding="utf-8") as file:
            content = yaml.safe_load(file)

        examples = []
        example_map = {}

        for item in content.get("nlu", []):
            for ex in item.get("examples", "").split("\n"):
                ex = ex.strip("- ").strip()
                if ex:
                    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", ex)
                    examples.append(cleaned)
                    example_map[cleaned] = ex

        user_msg = tracker.latest_message.get("text", "")
        print(f"User Message: {user_msg}")

        closest = difflib.get_close_matches(user_msg, examples, n=1, cutoff=0.5)

        if closest:
            cleaned_match = closest[0]
            annotated_match = example_map.get(cleaned_match)
            print(f"Closest Match: {annotated_match}")

            user_entities = {ent.get("entity"): ent.get("value") for ent in tracker.latest_message.get("entities", [])}
            print("User Entities:", user_entities)

            # Extract context words from matched training example
            def get_context_words(annotated):
                context = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", "", annotated)
                return set(re.findall(r"\w+", context.lower()))

            context_words = get_context_words(annotated_match)
            user_tokens = set(re.findall(r"\w+", user_msg.lower()))
            keyword_guess = " ".join(word for word in user_tokens if word not in context_words)
            print("Dynamically extracted keyword guess:", keyword_guess)

            # Replace entity in suggestion
            def replace_entity(match):
                entity_text = match.group(1)
                entity_type = match.group(2)
                return user_entities.get(entity_type) or keyword_guess or entity_text

            suggestion = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_entity, annotated_match)

            dispatcher.utter_message(text=f"I'm not sure I understood. Did you mean:\n➡️ '{suggestion}'?")
            return [SlotSet("suggested_message", suggestion)]

        # No close match at all
        dispatcher.utter_message(text="I'm sorry, I didn't quite understand. Could you rephrase that?")
        return []
