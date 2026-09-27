import sys,struct,zlib,os,collections
MAGIC=b'MEI\x0c\x0b\x0a\x0b\x0e'
def toc(fn):
    f=open(fn,'rb'); size=os.path.getsize(fn); f.seek(size-4096); tail=f.read()
    i=tail.rfind(MAGIC); cpos=size-4096+i
    pkglen,tocoff,toclen,pyver=struct.unpack('>IIII',tail[i+8:i+24])
    start=cpos+88-pkglen
    f.seek(start+tocoff); raw=f.read(toclen); p=0; out=[]
    while p<len(raw):
        es,off,cl,ul,flag,tc=struct.unpack('>IIIIBc',raw[p:p+18])
        name=raw[p+18:p+es].rstrip(b'\0').decode('utf-8','replace'); out.append((name,start+off,cl,ul,flag,tc.decode())); p+=es
    return f,out,pyver
if __name__=='__main__':
    mode,fn=sys.argv[1],sys.argv[2]
    f,entries,pyver=toc(fn)
    if mode=='list':
        c=collections.Counter(e[5] for e in entries); print('py',pyver,'entries',len(entries),dict(c))
        for n,o,cl,ul,fl,tc in entries:
            if tc!='b' or ul>200000 or not n.lower().endswith(('.dll','.pyd')): print(tc,ul,n)
    else:
        outdir=sys.argv[3]
        for n,o,cl,ul,fl,tc in entries:
            f.seek(o); d=f.read(cl)
            if fl: d=zlib.decompress(d)
            p=os.path.join(outdir,n.replace('/',os.sep)); 
            if tc in 's': p+='.pyc_body'
            os.makedirs(os.path.dirname(p) or outdir,exist_ok=True); open(p,'wb').write(d)
        print('extracted',len(entries))
