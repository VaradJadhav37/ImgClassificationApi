from flask import Flask, request
from flask_restful import Api, Resource
from pymongo import MongoClient
import bcrypt
import numpy as np
import requests
from tensorflow.keras.applications import InceptionV3
from tensorflow.keras.applications.inception_v3 import preprocess_input
from tensorflow.keras.applications import imagenet_utils
from tensorflow.keras.utils import img_to_array
from PIL import Image
from io import BytesIO

app = Flask(__name__)
api = Api(app)

client = MongoClient('mongodb+srv://VaradJ:varad21@cluster0.vpdku.mongodb.net/flask?retryWrites=true&w=majority&appName=Cluster0')
db = client.ImageRecognition
users = db["users"]
pretrained_model = InceptionV3(weights='imagenet')

def verifyPw(username, password):
    user = users.find_one({"username": username})
    if not user:
        return False
    hashedpwd = user["password"]
    return bcrypt.checkpw(password.encode('utf-8'), hashedpwd)

def countTokens(username):
    user = users.find_one({"username": username})
    return user["tokens"] if user else 0

class Register(Resource):
    def post(self):
        data = request.get_json()
        username = data['username']
        password = data['password']
        if users.find_one({"username": username}):
            return {"message": "Username already exists"}, 400
        hashedpwd = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        users.insert_one({"username": username, "password": hashedpwd, "tokens": 6})
        return {"message": "User registered successfully"}, 201

class Classify(Resource):
    def post(self):
        data = request.get_json()
        username = data['username']
        password = data['password']
        if not verifyPw(username, password):
            return {"message": "Invalid credentials"}, 401
        
        tokens = countTokens(username)
        if tokens <= 0:
            return {"message": "No tokens left"}, 403
        
        image_url = data['image_url']
        if not image_url:
            return {"message": "No image URL provided"}, 400
        
        try:
            response = requests.get(image_url)
            img = Image.open(BytesIO(response.content))
            img = img.resize((299, 299))
            x = img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)

            pred = pretrained_model.predict(x)
            actual_preds = imagenet_utils.decode_predictions(pred, top=5)
            
            # Deduct token only after successful processing
            users.update_one({"username": username}, {"$set": {"tokens": tokens - 1}})
            
            ret_json = {}
            for pred in actual_preds[0]:
                ret_json[pred[1]] = float(pred[2] * 100)
            return ret_json, 200
        
        except Exception as e:
            return {"message": f"Error processing image: {str(e)}"}, 500

class Refill(Resource):
    def post(self):
        data = request.get_json()
        username = data['username']
        password = data['password']
        refill_amount = data['refill_amount']
        
        if refill_amount < 0:
            return {"message": "Invalid refill amount"}, 400
        
        if not verifyPw(username, password):
            return {"message": "Incorrect password"}, 401
        
        current_tokens = countTokens(username)
        users.update_one(
            {"username": username},
            {"$set": {"tokens": current_tokens + refill_amount}}
        )
        return {"message": "Tokens refilled successfully"}, 200

api.add_resource(Register, '/register')
api.add_resource(Classify, '/classify')
api.add_resource(Refill, '/refill')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)