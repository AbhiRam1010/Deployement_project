from django.shortcuts import render
from .forms import *
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth import authenticate,login,logout
from master.models import Item
from django.urls import reverse
# Create your views here.
def home(request):
    return render(request,'home.html')

def user_regitration(request):
    EUFO= CostumerForm()
    d={'EUFO':EUFO}
    if request.method == 'POST':
        UFDO=CostumerForm(request.POST)
        if UFDO.is_valid():
            pw=UFDO.cleaned_data['password']
            MFDO=UFDO.save(commit=False)
            MFDO.set_password(pw)
            MFDO.save()
            return HttpResponse('You are registered to Zomato')
    return render(request,'user_regitration.html',d)

def user_login(request):
    if request.method == 'POST':
        un=request.POST.get('un')
        pw=request.POST.get('pw')
        UO=User.objects.get(username=un)
        AMO=authenticate(username=un,password=pw)
        if AMO and AMO.is_active:
            login(request,AMO)
            request.session['username']=un
            if UO.is_staff :
                return render (request,'additem.html')
            return HttpResponseRedirect(reverse('home'))
    return render (request,'login.html')

def go_to_menu(request):
    d={'items':Item.objects.all()}
    return render(request,'user_menu.html',d)

def user_logout(request):
    logout(request)
    return render (request,'home.html')

def add_cart(request,pk):
    if request.method=='POST':
        qty=request.POST.get('qty')
        IO=Item.objects.get(item_id=pk)
        un=User.objects.get(username=request.session['username'])
        print(IO,un)
        try:
            CO=Cart.objects.get(cart_id=un,name=IO)
            CO.name==IO
            CO.qty+=int(qty)
            CO.save()
        except Cart.DoesNotExist:
            CO=Cart(cart_id=un,price=IO.item_price,qty=qty,name=IO.item_name)
            CO.save()
        return HttpResponseRedirect(reverse('cart'))
    return HttpResponseRedirect(reverse('go_to_menu'))


# def cart(request):
#     CO=Cart.objects.get(cart_id=request.sessio['username'])
#     d={'CO':CO}
#     for i in d:
#         i['total']=i['qty']*i['price']    
#     return render(request,'cart.html',d)


def cart(request):
    Grand_total=0
    UO=Cart.objects.all()
    CO=list(filter(lambda i: i.cart_id.username== request.session['username'], UO))
    for i in CO:
        i.total=i.qty*i.price
        Grand_total+= i.total
    d={'CO':CO,'Grand_total':Grand_total}
    return render(request,'cart.html',d)


def Buy(request):
   UO=Cart.objects.all()
   try:
        CO=list(filter(lambda i: i.cart_id.username== request.session['username'], UO))
        for i in CO:
            i.delete()
            i.save()
   except:
       print('No cart present')
   return HttpResponse('YOUr Order is placed "Thank You For Shoping With Us"')