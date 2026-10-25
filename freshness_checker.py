from datetime import datetime, timedelta

def check_freshness(last_refresh_time, delta):
     
     """
    Check whether the data satisfies the freshness limit.

    Parameters:
        last_refresh_time: datetime when the data was last refreshed
        delta: maximum allowed data age in minutes

    Returns:
        age_minutes: current age of the data
        is_fresh: True if age <= delta, otherwise False
    """

     current_time = datetime.now()
     age = current_time - last_refresh_time 
     age_minutes = round(age.total_seconds() / 60, 2)

     is_fresh = age_minutes <= delta

     return age_minutes, is_fresh

if __name__ == "__main__":
     last_refresh_time = datetime.now() - timedelta(minutes=10)

     delta = 10
     age, is_fresh = check_freshness(last_refresh_time, delta)

     print("Data age:", round(age, 2), "minutes.")
     print("Freshness Limit:", delta, "minutes")
     print("Freshness Status:", is_fresh)
