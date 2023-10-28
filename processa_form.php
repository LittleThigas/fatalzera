<?php
if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $email = $_POST["email"];

    $destinatario = "fatalzerax@gmail.com"; // Substitua pelo seu endereço de email
    $assunto = "Novo email do formulário do site";

    // Mensagem de email
    $mensagem = "Email: " . $email;

    // Envia o email
    mail($destinatario, $assunto, $mensagem);

    // Redireciona para uma página de confirmação
    header("Location: index.html");
}
?>
