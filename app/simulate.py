"""Small simulation against the running local API."""
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def request(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode())

def main():
    print("Creating agents and borrowers...")
    print(request("/agents/bulk", "POST", {"count": 5}))
    print(request("/borrowers/bulk", "POST", {"count": 12}))
    print("\nProgressive dialing:")
    print(json.dumps(request("/dial/progressive", "POST",
          {"campaign_id": "simulation", "provider": "fast", "max_calls": 5}), indent=2))
    print("\nMetrics:")
    print(json.dumps(request("/metrics"), indent=2))
    print("\nTip: use /provider-events to simulate RINGING, ANSWERED, CONNECTED, and COMPLETED.")

if __name__ == "__main__":
    main()
