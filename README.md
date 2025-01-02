# Creating a Telegram bot

Documenting my first telegram bot that runs on AWS Lambda (webhook) and stores data using AWS DynamoDB.

## Features of inventory-list-bot

App to track household items inventory, consumption rates, and eventually create a simple forecast/alert system (pending more data). 

Commonly used feature commands: 
1. Add \<item> - Add new or existing items to inventory
2. Get \<item> - Retrieve current item count in inventory
3. Consume \<item> - Record items being consumed, and reduce inventory count

Other notes/features:
* When commands are used without specifying an item name, an inline keyboard with all existing items in the inventory will appear for the user to select. The selection is then handled using a callback query.

* Inventories are tied to specific chats - Different chats will not be able to read each other's inventory, even if there are common users.

* Only whitelisted chats are allowed to use this bot.

Versions:
* Python 3.13
* telebot 4.16.1
* boto3 1.34.145

## Setup required in Telegram and AWS
### 1. Create the bot in telegram
* In telegram, search for @botfather and message "/start"
* Choose a name, username, and retrieve the `TOKEN` (e.g. 12345:ABCDE) that is generated.
* Send a message to the new bot. Replace your `TOKEN` and go to this url `https://api.telegram.org/bot<TOKEN>/getUpdates` to retrieve your `CHATID`
* (Optional) To test the bot, send a message using the URL `https://api.telegram.org/bot<TOKEN>/sendMessage?chat_id=<CHATID>&text=Hi`

### 2. Setup AWS Lambda
* Go to AWS Console > Lambda > Create function
* Enter a function name, set Python 3.13 as runtime, select "Enable function URL" with "Auth type" = NONE under Additional Configurations
* In your lambda function, under the "Configuration" tab > "Environment Variables", save the `TOKEN` as an environment variable. This allows the lambda function to access your variables (through os.environ)
* Under the function overview, copy the `Function URL` to be used for setting the webhook later.
* You may start to develop the code (`lambda_function.py`)

### 3. Configure layer for additional dependencies (Python)
* Prepare a zip file with the dependencies that are required by your function but are not available by default in Lambda (refer to `python_layer.zip` in this repo)
* From your Lambda dashboard (not your function), go to "Layers" (under Additional resources), click on "Create layer".  Upload the zip file, fill in the necessary details, and create the layer.
* Go back to your lambda function, click on "Layers", then "Add a layer". Select "custom layer", then choose the layer than you just created.

### 4. Setting up DynamoDB tables to store data
* Go to AWS Console > DynamoDB > Tables > Create table
* Enter table name and keys, change "Table settings" to "Customize settings", change "Read/write capacity settings" to "Provisioned", and "Auto scaling" to "Off"
* Go to AWS Cinsole > IAM > Roles, click on the role assigned to your lambda function (functionname-role-xxx). Under "Permissions policies" > "Add permissions" > Attach the policy "AmazonDynamoDBFullAccess"
* To use the table in your Lambda function, put it as an environment variable and call it

### 5. Developing and deploying the function
* To test the code, create a test event json (Refer to `test_event_help_command.json` in this repo for the body of a sample request that sends the /help command. Change the `CHATID` to receive replies from the bot)
* Once ready to deploy, set the webhook by calling this url `https://api.telegram.org/bot<TOKEN>/setWebhook?url=<Function URL>` (Replace the Token and URL)
* To delete the webhook, simply change the command in the previous url from "setWebhook" to "deleteWebhook"
* To check the status of the webhook, go to `https://api.telegram.org/<TOKEN>/getWebhookInfo`
* For troubleshooing, logs are stored in CloudWatch (From AWS console) > Log groups