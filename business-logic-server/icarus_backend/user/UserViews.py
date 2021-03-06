from django.template.response import TemplateResponse
from rest_framework.decorators import api_view
from django.http import HttpResponse
import json
from users.models import IcarusUser as User
from icarus_backend.pilot.PilotModel import Pilot
from users.tokens import account_activation_token
from django.utils.encoding import force_text
from django.utils.http import urlsafe_base64_decode
from icarus_backend.user.tasks import send_verification_email, reset_password_email
from django.contrib.sites.shortcuts import get_current_site
from icarus_backend.utils import validate_body
from oauth2_provider.decorators import protected_resource
from .userViewSchemas import *
from icarus_backend.user.UserController import UserController


@api_view(['POST'])
@validate_body(register_user_schema)
def icarus_register_user(request):
    body = request.data
    username = body['username']
    password = body['password']
    email = body['email']
    first_name = body['first_name']
    last_name = body['last_name']
    domain = get_current_site(request).domain
    status, message = UserController.register_user(username, email, password,
                                                   first_name, last_name, domain)
    response_data = {'message': message}
    response_json = json.dumps(response_data)
    return HttpResponse(response_json, content_type="application/json", status=status)


@protected_resource()
@api_view(['GET'])
def icarus_get_current_user(request):
    response_dict = dict()
    response_dict['user'] = request.user.as_dict()
    pilot = Pilot.objects.filter(user=request.user).first()
    if pilot:
        response_dict['pilot'] = pilot.as_dict()
    response_json = json.dumps(response_dict)
    return HttpResponse(response_json, content_type="application/json", status=200)


@protected_resource()
@api_view(['GET'])
def icarus_get_user(request):
    id = request.query_params.get('id')
    status, response_dict = UserController.get_user(id)
    response_json = json.dumps(response_dict)
    return HttpResponse(response_json, content_type="application/json", status=status)


@protected_resource()
@api_view(['POST'])
@validate_body(update_user_info_schema)
def update_user_info(request):
    parsed_json = request.data
    status, data = UserController.update(request.user.id, parsed_json)
    return HttpResponse(json.dumps(data), content_type="application/json", status=status)


@api_view(['GET'])
def icarus_is_logged_in(request):
    if request.user.is_active:
        response_json = json.dumps(True)
        return HttpResponse(response_json, content_type="application/json", status=200)
    else:
        response_json = json.dumps(False)
        return HttpResponse(response_json, content_type="application/json", status=200)


@api_view(['GET'])
def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=int(uid))
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user.username, token):
        user.is_active = True
        user.save()
        # return redirect('home')
        return HttpResponse('Thank you for your email confirmation. Now you can login your account.')
    else:
        return HttpResponse('Activation link is invalid!')


@api_view(['GET'])
def forgot_password(request):
    email = request.query_params.get('email')
    user = User.objects.filter(email=email).first()
    if user:
        domain = get_current_site(request).domain
        reset_password_email.delay(user.username, user.email, user.id, domain)
    response_data = {'message': 'If your account exists a password reset email is being sent.'}
    response_json = json.dumps(response_data)
    return HttpResponse(response_json, content_type="application/json")


@api_view(['GET', 'POST'])
def reset_password_token(request, uidb64, token):
    if request.method == 'GET':
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=int(uid))
            validlink = True
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
            validlink = False
        return TemplateResponse(request, 'password_reset_confirm.html', {
            'validlink': validlink,
            'uid': uidb64,
            'token': token
            })
    elif request.method == 'POST':
        try:
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=int(uid))
            validlink = True
        except(TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
            validlink = False
        if user is not None and account_activation_token.check_token(user.username, token):
            body = request.data
            new_password = body['new_password']
            user.set_password(new_password)
            user.save()
            # return redirect('home')
            return HttpResponse('Your password has been updated. Now you can login your account.')
        else:
            return HttpResponse('Activation link is invalid!')


@protected_resource()
@api_view(['POST'])
@validate_body(change_password_schema)
def change_password(request):
    body = request.data
    old_password = body['old_password']
    new_password = body['new_password']
    status, message = UserController.change_password(request.user.email, old_password,
                                                     new_password)
    response_data = {'message': message}
    response_json = json.dumps(response_data)
    return HttpResponse(response_json, content_type="application/json", status=status)