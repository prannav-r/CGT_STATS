for i in fdata:
        total=0
        c=1
        for j in i:
            if c>1:
                total+=i[j]
            out+=f"{j:<20}{i[j]}\n"
            c+=1
        out+="Total Fantasy Points = "
        out+=f"{total}\n\n\n"