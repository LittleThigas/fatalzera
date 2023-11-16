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
            echo "<script>
                    var successMessage = document.createElement('div');
                    successMessage.innerHTML = 'E-mail enviado com sucesso!';
                    successMessage.className = 'alert success';
                    document.body.appendChild(successMessage);
                  </script>";
        } else {
            echo "<script>
                    var errorMessage = document.createElement('div');
                    errorMessage.innerHTML = 'Houve um erro ao enviar o email!';
                    errorMessage.className = 'alert error';
                    document.body.appendChild(errorMessage);
                  </script>";
        }
        
?>

<style>
    .alert {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        padding: 15px;
        border-radius: 10px;
        color: #fff;
        font-size: 18px;
        font-weight: bold;
        text-align: center;
        z-index: 9999;
        width: 300px; /* Ajuste a largura conforme necessário */
    }

    .success {
        background-color: #4CAF50; /* Cor de fundo para sucesso */
    }

    .error {
        background-color: #f44336; /* Cor de fundo para erro */
    }
</style>
