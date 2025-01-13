import pickle


fp={1,2,3,4,5}
with open('fpdbs.pkl','ab') as f:
        pickle.dump(fp,f)


fdata=[]
with open('fpdbs.pkl', 'rb') as fr:
        try:
            while True:
                fdata.append(pickle.load(fr))
        except EOFError:
            pass

print(fdata)