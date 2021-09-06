# Import libraries
from flask import Flask
from flask import request
import requests
import json
import mysql.connector
import random


# ------------------------------------------------------------------------------
# ----------------------- Define the auxiliary functions -----------------------
# ------------------------------------------------------------------------------

# STATIC variables
OPENUV_URL_RECENT = "https://api.openuv.io/api/v1/uv"

# This function reads the text file contains the API keys and randomly return 1 of them
def get_api_key():
    all_keys = []
    f = open('open_uv_api_keys.txt', 'r')
    lines = f.readlines()
    for l in lines:
        all_keys.append(str(l).rstrip())
    return random.choice(all_keys)


# This function return a connection to the database
def connect_to_db():
    # Get azure authentication
    all_info = []
    f = open('azure_database_authentication.txt', 'r')
    lines = f.readlines()
    for l in lines:
        all_info.append(str(l).rstrip())
        
    db_info = {
        'server_name': all_info[0],
        'user_name': all_info[1],
        'pwd': all_info[2],
        'db_name': all_info[3] 
    }

    return mysql.connector.connect(
        host=db_info['server_name'],
        user=db_info['user_name'],
        password=db_info['pwd'],
        database=db_info['db_name']
    )


# This function find the given suburb info from the database
def find_coordinate(postcode):
    db_connection = connect_to_db()
    db_cursor = db_connection.cursor()
    
    # If valid post code then return actual result
    try:
        db_cursor.execute("SELECT * FROM suburbs WHERE postcode="+postcode)
        record = db_cursor.fetchall()[0]
        coord = {
            'lat': record[4],
            'lng': record[3]
        }
        suburb_info = {
            'postcode': record[1],
            'name': record[2]
        }
    # If invalid post code then return default result
    except Exception:
        coord = {
            'lat': '-37.817403',
            'lng': '144.956776'
        }
        suburb_info = {
            'postcode': '3000',
            'name': 'Default postcode: 3000'
        }
    finally:
        return [coord, suburb_info]


# Define the function to evaluate the UVR
def evaluate_uvr(uvr):
    if uvr<=2:
        return 'low'
    elif uvr>2 and uvr<=5:
        return 'relative low'
    elif uvr>5 and uvr<=7:
        return 'moderate'
    elif uvr>7 and uvr<=10:
        return 'high'
    else:
        return 'extremely high'


# -----------------------------------------------------------------------
# ------------------------ Create the Aplication ------------------------
# -----------------------------------------------------------------------
app = Flask(__name__)


# -------------------------------------------------------------------------------
# ------------------------------ Generate the APIs ------------------------------
# -------------------------------------------------------------------------------


# ------------------------------------- ITERATION 1 -------------------------------------

# API to get current UVR for a specific location (Iteration 1)
@app.route('/uvr_location')
def uvr_location():

    postcode = request.args.get('postcode')
    
    # Get coordinates from database
    PARAMS = find_coordinate(postcode)[0]
    suburb_info = find_coordinate(postcode)[1]

    # Send API request to OpenUV
    req = requests.get(url=OPENUV_URL_RECENT, params=PARAMS, headers={"x-access-token": get_api_key()})
    data = json.loads(req.text)
    
    # Compose and return result data
    result = {
        'postcode': postcode,
        'suburb': suburb_info['name'],
        'UVR': data['result']['uv'],
        'max_UVR': data['result']['uv_max']
    }
    return str(result)


# API to get current UVR for 18 most crowded suburbs in Melbourne (Iteration 1)
@app.route('/uvr_inner_suburbs')
def uvr_inner_suburbs():
    # 18 most crowded suburbs in Melbourne
    INNER_SUBURBS = ['3000', '3121', '3182', '3056', '3141', '3051', 
                    '3181', '3053', '3006', '3183', '3207', '3184', 
                    '3068', '3057', '3031', '3065', '3162', '3168']

    # List of data to return
    result=[]

    # Get data for each postcode
    for postcode in INNER_SUBURBS:
        # Get coordinates from database
        PARAMS = find_coordinate(postcode)[0]
        suburb_info = find_coordinate(postcode)[1]
        
        # Send API request to OpenUV
        req = requests.get(url=OPENUV_URL_RECENT, params=PARAMS, headers={"x-access-token": get_api_key()})
        data = json.loads(req.text)
        
        # Compose result data
        result.append({
            'postcode': postcode,
            'suburb': suburb_info['name'],
            'UVR': data['result']['uv'],
            'max_UVR': data['result']['uv_max']
        })
    return str(result)


# API to get historical UVR group by Months (Iteration 1)
@app.route('/uvr_by_month')
def uv_by_month():
    # Create connection to database
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()
    db_cursor.execute("SELECT * FROM uvr")
    records = db_cursor.fetchall()

    # List of data to return
    result = []

    # Compose and return result data
    for rec in records:
        result.append({
            'month': rec[1],
            'year': rec[2],
            'avg_UVR': rec[3]
        })
    return str(result)


# API to get historical UVR group by Years (Iteration 1)
@app.route('/uvr_by_year')
def uvr_by_year():
    # Create connection to database
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()
    db_cursor.execute("SELECT year, AVG(uv_index) AS avg_uv FROM uvr GROUP BY year")
    records = db_cursor.fetchall()

    # List of data to return
    result = []

    # Compose and return result data
    for rec in records:
        result.append({
            'year': rec[0],
            'avg_UVR': rec[1]
        })
    return str(result)


# API to get protectors based on UVR (Iteration 1)
@app.route('/uvr_protector')
def uvr_protector():

    uvr = float(request.args.get('uvr'))
    uvr_rating = evaluate_uvr(uvr)

    result = []
    
    # Query data from DB
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()

    # Find the hats
    db_cursor.execute("SELECT * FROM hat WHERE UVR='"+uvr_rating+"'")
    records = db_cursor.fetchall()
    
    # Compose result data
    for rec in records:
        result.append({
            'type': 'hat',
            'hat_type': rec[2],
            'forehead': rec[3],
            'cheek': rec[4],
            'nose': rec[5],
            'ear': rec[6],
            'chin': rec[7],
            'neck': rec[8],
        })
    
    # Find the sunglasses
    db_cursor.execute("SELECT * FROM sunglasses WHERE UVR='"+uvr_rating+"'")
    records = db_cursor.fetchall()
    
    # Compose result data
    for rec in records:
        result.append({
            'type': 'sunglasses',
            'lens_category': rec[2],
            'function': rec[3],
            'situation': rec[4],
            'glare': rec[5]
        })

    # Find the sunscreen
    db_cursor.execute("SELECT * FROM sunscreen WHERE UVR='"+uvr_rating+"'")
    records = db_cursor.fetchall()
    
    # Compose result data
    for rec in records:
        if rec[2] == '1':
            pa_str = 'PA+'
        elif rec[2] == '2':
            pa_str = 'PA++'
        elif rec[2] == '3':
            pa_str = 'PA+++'
        elif rec[2] == '4':
            pa_str = 'PA++++'
        else:
            pa_str = 'PA+'

        result.append({
            'type': 'sunscreen',
            'PA': pa_str,
            'desc': rec[3],
            'SPF': rec[4],
            'UVB_percentage': rec[5],
            'situation': rec[6]
        })

    # Find the clohtes
    db_cursor.execute("SELECT * FROM umbrella_clothes WHERE UVB='"+uvr_rating+"'")
    records = db_cursor.fetchall()
    
    # Compose result data
    for rec in records:
        result.append({
            'type': 'umbrella_clothes',
            'UPF': rec[2],
            'UVB_percentage': rec[3]
        })

    return str(result)


# API to return 1 single protector (Iteration 1)
@app.route('/single_protector')
def single_protector():

    protector_name = request.args.get('protector_name')

    # Query data from DB
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()

    result = []

    # Get all hats
    if protector_name == 'hat':
        db_cursor.execute("SELECT * FROM "+protector_name)
        records = db_cursor.fetchall()
        
        # Compose result data
        for rec in records:
            result.append({
                'hat_type': rec[2],
                'forehead': rec[3],
                'cheek': rec[4],
                'nose': rec[5],
                'ear': rec[6],
                'chin': rec[7],
                'neck': rec[8],
            })
    # Get all sunglasses
    elif protector_name == 'sunglasses':
        db_cursor.execute("SELECT * FROM "+protector_name)
        records = db_cursor.fetchall()
        
        # Compose result data
        for rec in records:
            result.append({
                'lens_category': rec[2],
                'function': rec[3],
                'situation': rec[4],
                'glare': rec[5]
            })
    # Get all sunscreen
    elif protector_name == 'sunscreen':
        db_cursor.execute("SELECT * FROM "+protector_name)
        records = db_cursor.fetchall()
        
        # Compose result data
        for rec in records:
            result.append({
                'PA': rec[2],
                'desc': rec[3],
                'SPF': rec[4],
                'UVB_percentage': rec[5],
                'situation': rec[6]
            })
    # Get all umbrella_clothes
    elif protector_name == 'umbrella_clothes':
        db_cursor.execute("SELECT * FROM "+protector_name)
        records = db_cursor.fetchall()
        
        # Compose result data
        for rec in records:
            result.append({
                'UPF': rec[2],
                'UVB_percentage': rec[3]
            })
    else:   
        return "Invalid Request"

    return str(result)


#  API to return all protectors (Iteration 1)
@app.route('/all_protectors')
def all_protectors():

    result = {}

    # Query data from DB
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()


    # Get all sunglasses
    temp = []
    db_cursor.execute("SELECT * FROM sunglasses")
    records = db_cursor.fetchall()
    
    # Compose temp data
    for rec in records:
        temp.append({
            'lens_category': rec[2],
            'function': rec[3],
            'situation': rec[4],
            'glare': rec[5]
        })
    # Compose result data
    result['sunglasses'] = temp


    # Get all hat
    temp = []
    db_cursor.execute("SELECT * FROM hat")
    records = db_cursor.fetchall()
    
    # Compose temp data
    for rec in records:
        temp.append({
            'hat_type': rec[2],
            'forehead': rec[3],
            'cheek': rec[4],
            'nose': rec[5],
            'ear': rec[6],
            'chin': rec[7],
            'neck': rec[8],
        })
    # Compose result data
    result['hat'] = temp


    # Get all sunscreen
    temp = []
    db_cursor.execute("SELECT * FROM sunscreen")
    records = db_cursor.fetchall()
    
    # Compose temp data
    for rec in records:
        temp.append({
            'PA': rec[2],
            'desc': rec[3],
            'SPF': rec[4],
            'UVB_percentage': rec[5],
            'situation': rec[6]
        })
    # Compose result data
    result['sunscreen'] = temp


    # Get all umbrella_clothes
    temp = []
    db_cursor.execute("SELECT * FROM umbrella_clothes")
    records = db_cursor.fetchall()
    
    # Compose temp data
    for rec in records:
        temp.append({
            'UPF': rec[2],
            'UVB_percentage': rec[3]
        })
    # Compose result data
    result['umbrella_clothes'] = temp
    
    return str(result)



# ------------------------------------- ITERATION 2 -------------------------------------

# API to get current UVR for a specific location (Iteration 2)
@app.route('/uvr_location_i2')
def uvr_location_i2():

    postcode = request.args.get('postcode')
    
    # Get coordinates from database
    PARAMS = find_coordinate(postcode)[0]
    suburb_info = find_coordinate(postcode)[1]

    # Send API request to OpenUV
    req = requests.get(url=OPENUV_URL_RECENT, params=PARAMS, headers={"x-access-token": get_api_key()})
    data = json.loads(req.text)
    
    # Compose and return result data
    result = {
        'postcode': postcode,
        'suburb': suburb_info['name'],
        'UVR': data['result']['uv'],
        'max_UVR': data['result']['uv_max'],
        'lat': PARAMS['lat'],
        'lng': PARAMS['lng']
    }
    return str(result)


# API to get historical UVR group by Months (Iteration 2)
@app.route('/uv_by_month_i2')
def uv_by_month_i2():
    # Create connection to database
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()
    db_cursor.execute("SELECT month, AVG(uv_index) AS avg_uv FROM uvr GROUP BY month ORDER BY month ASC")
    records = db_cursor.fetchall()

    # List of data to return
    result = []

    # Compose and return result data
    for rec in records:
        result.append(rec[1])
    
    # Data is a list of Average UVR from [Jan, Feb, Mar,..., Dec]
    return str(result)


# API to get historical UVR group by Years (Iteration 2)
@app.route('/uv_by_year_i2')
def uv_by_year_i2():
    # Create connection to database
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()
    db_cursor.execute("SELECT year, AVG(uv_index) AS avg_uv FROM uvr GROUP BY year ORDER BY year ASC")
    records = db_cursor.fetchall()

    # List of data to return
    result = []

    # Compose and return result data
    for rec in records:
        result.append(rec[1])

    # Data is a list of Average UVR from [2010, 2011, 2012,..., 2020]
    return str(result)


# API to get hospitals by postcode (Iteration 2)
@app.route('/nearby_hospitals_i2')
def nearby_hospitals_i2():

    postcode = request.args.get('postcode')
    result = []
    
    # Query data from DB
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()

    # If the postcode is valid then return hospitals nearby
    try:
        # Find the hospitals
        db_cursor.execute("SELECT * FROM hospitals WHERE Postcode="+postcode)
        records = db_cursor.fetchall()
        
        # Compose result data
        for rec in records:
            result.append({
                'name': rec[1],
                'phone': rec[2],
                'address': rec[3],
                'suburb': rec[4],
                'postcode': rec[5],
                'state': rec[6],
                'sector': rec[7],
                'lat': rec[8],
                'lng': rec[9]
            })
    # If the postcode is invalid then return default hospital
    except Exception:
        result.append({
                'name': "Default hospital for invalid postcode: Royal Melbourne Hospital [Parkville]",
                'phone': "03 9342 7000",
                'address': '300 Grattan Street',
                'suburb': 'Parkville',
                'postcode': 3050,
                'state': 'Vic',
                'sector': 'Public',
                'lat': -37.799259,
                'lng': 144.956864
            })
    finally:
        if len(records)==0:
            result.append({
                'name': "Default hospital for invalid postcode: Royal Melbourne Hospital [Parkville]",
                'phone': "03 9342 7000",
                'address': '300 Grattan Street',
                'suburb': 'Parkville',
                'postcode': 3050,
                'state': 'Vic',
                'sector': 'Public',
                'lat': -37.799259,
                'lng': 144.956864
            })

        return str(result)

    
# API to get quizzes (Iteration 2)
@app.route('/quiz_i2')
def quiz_i2():
    all_topics = ['Eye_dmg', 'Skin_dmg', 'Sunscreen', 'Sunglasses', 'Hat', 'Cloth', 'UVR']
    
    result = []

    # Query data from DB
    db_connection = connect_to_db()

    # Create and execute SQL query
    db_cursor = db_connection.cursor()

    # Get 1 random question for each topic
    for topic in all_topics:
        db_cursor.execute("SELECT * FROM quiz WHERE Topic='{}' ORDER BY RAND() LIMIT 1".format(topic))
        records = db_cursor.fetchall()

        # Compose the result
        for rec in records:
            result.append({
                'topic': rec[1],
                'question': rec[2],
                'answer': rec[3],
                'explanation': rec[4],
                'selection_1': rec[5],
                'selection_2': rec[6]
            })

    # Return the result
    return str(result)


# ------------------------------------- ITERATION 3 -------------------------------------
# (Comming soon)

# --------------------------------------------------------------------------------------
# --------------------------- Start the main API application ---------------------------
# --------------------------------------------------------------------------------------
if __name__ == '__main__':
    app.run()