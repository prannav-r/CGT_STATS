import pickle
    
fdata=[]
with open('fpdbs.pkl', 'rb') as fr:
    try:
        while True:
            fdata.append(pickle.load(fr))
    except EOFError:
        pass
    
# with open('fpdbs.pkl', 'wb') as fr:
#     fr.close()
# c=1
# for i in fdata:
#     if c!=5:
#         c+=1
#         with open('fpdbs.pkl', 'ab') as f:
#             pickle.dump(i, f)
#     else:
#         fdata.remove(i)

# for i in fdata:
#     with open('fpdbs.pkl', 'ab') as f:
#             pickle.dump(i, f)


# with open('fpdbs.pkl', 'ab') as f:
#         pickle.dump(fdata, f)
print(fdata)