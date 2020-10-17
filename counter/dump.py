import requests

r = requests.get('http://localhost:5100/getAllKeysAndValues')

print(r.text)
