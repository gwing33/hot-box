# send_api_request('/api/data', data={'temp': 25.5}, method='POST')

# Function to send API requests to local endpoint
def send_api_request(endpoint, data=None, method='GET'):
    try:
        from secrets import API_HOST, API_PORT
    except ImportError:
        print("Warning: API_HOST or API_PORT not found in secrets.py")
        return None

    import urequests

    url = f'http://{API_HOST}:{API_PORT}{endpoint}'

    try:
        if method == 'GET':
            response = urequests.get(url)
        elif method == 'POST':
            response = urequests.post(url, json=data)
        elif method == 'PUT':
            response = urequests.put(url, json=data)
        else:
            print(f'Unsupported method: {method}')
            return None

        status = response.status_code
        content = response.text
        response.close()

        print(f'API {method} {endpoint}: {status}')
        return {'status': status, 'content': content}

    except Exception as e:
        print(f'API request failed: {e}')
        return None
