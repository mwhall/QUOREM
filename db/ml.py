import pandas as pd

from .models import *

def feature_select(countmatrix_pk, method='variance', n_features=100):
    #### FUNCTION FROM JUPYTER GOES HERE
    results = pd.DataFrame(['a','b','c'])
    #Store results in a Pandas DataFrame
    #Return results.style
    #Return an HTML table representing the list of features that survived selection
    return results.style.to_html()

# I'M ADDING A COMMENT