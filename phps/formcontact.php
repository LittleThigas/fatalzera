<?php

    $nome = addcslashes($_POST['name']);
    $email = addcslashes($_POST['email']);
    $telefone = addcslashes($_POST['telefone']);

    $para = "fatalzerax@gmail.com";
    $assunto = "Coleta de Dados - Fatalzera";
    
    $corpo = "Nome: ".$nome."\n"."Email: ".$email."\n"."Telefone: ".$telefone;

    $cabeca = "From fatalzera@site.com"."\n"."reply-to: ".$email. "\n"."X=Mailer:PHP/".phpversion();

    if(mail($para, $assunto, $corpo, $cabeca)) {
        if(mail($para, $assunto, $corpo, $cabeca)) {
            echo ("E-mail enviado com sucesso!");
        }else{
        echo ("Houve um erro ao enviar o email!");
        }
        
?>
