import pickle

# Replace 'path_to_your_file.pkl' with the actual path to your PKL file
file_path = 'b_statsS2.pkl'

# Open the file in binary mode and load the data
with open(file_path, 'rb') as file:
    data = pickle.load(file)

# Now 'data' contains the deserialized Python object
print(data)
