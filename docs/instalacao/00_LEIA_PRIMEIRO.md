# Instalação da Academia Técnica — comece aqui

Edição: 8 de setembro de 2026 · Público: equipe que receberá e instalará a plataforma.

Este pacote contém quatro manuais. Escolha **somente o par correspondente ao sistema do servidor**. Não execute os quatro no mesmo computador.

Para usar o pacote ZIP: clique com o botão direito → **Extrair tudo** e abra `index.html` na pasta extraída. As páginas funcionam sem internet para leitura; downloads dos programas e links dos fornecedores exigem conexão. Use o botão **Imprimir ou salvar em PDF**, escolha a impressora ou o destino **Salvar como PDF** e papel A4. Para copiar comandos, prefira o texto da página HTML; linhas longas podem quebrar visualmente no PDF. Os arquivos `.md` são as versões de texto editáveis.

| Servidor | Primeiro: banco de dados | Depois: plataforma |
|---|---|---|
| Windows Server 2022 ou 2025, com interface gráfica, 64 bits | [PostgreSQL no Windows](01_POSTGRESQL_WINDOWS.md) | [Plataforma no Windows](02_PLATAFORMA_WINDOWS.md) |
| Ubuntu Server 24.04 LTS, 64 bits | [PostgreSQL no Ubuntu](03_POSTGRESQL_UBUNTU.md) | [Plataforma no Ubuntu](04_PLATAFORMA_UBUNTU.md) |

Linux tem várias distribuições. Os comandos deste pacote são para **Ubuntu 24.04**, não para Debian, Red Hat, Rocky, CentOS ou qualquer Linux indistintamente. Windows Server Core, sem área de trabalho, também não é o cenário deste roteiro. Se o servidor tiver outro sistema, entregue este pacote à TI para adaptar ou disponibilizar uma máquina virtual com um dos sistemas acima.

## 1. O que será montado

```text
Computador/celular do usuário
           |
     Internet — HTTPS, porta 443
           |
Firewall/roteador da empresa
           |
Servidor da plataforma
  Caddy: recebe o acesso e fornece HTTPS, CSS, vídeos locais e PDFs
       |
  Waitress (Windows) ou Gunicorn (Ubuntu): executa o Django
       |
  PostgreSQL: guarda usuários, cursos, respostas e certificados
```

O cenário principal é **uma máquina dedicada ou máquina virtual**, com aplicação e banco juntos. Os usuários acessam apenas o site. Não instalam Python, PostgreSQL ou a plataforma nas próprias máquinas.

O sistema operacional deve estar instalado, atualizado e com rede funcionando. Este pacote não ensina a formatar o servidor. Não reutilize estes passos às cegas em servidor que já hospeda outros sistemas: portas, bancos e configurações podem estar em uso.

## 2. O que pedir à TI antes de começar

Preencha e entregue a ficha abaixo ao instalador. Os valores de exemplo não são os dados reais da empresa.

| Informação | Exemplo ou orientação | Valor real |
|---|---|---|
| Sistema e versão | Windows Server 2022/2025 ou Ubuntu 24.04 | __________________ |
| Nome do servidor | SRV-ACADEMIA | __________________ |
| IP fixo na rede interna | 192.168.10.50 | __________________ |
| Endereço público do site | treinamentos.suaempresa.com.br | __________________ |
| IP público de entrada | Informado pelo responsável pela internet | __________________ |
| Responsável por DNS/firewall | Nome e contato | __________________ |
| Conta administrativa do servidor | Guardar senha no cofre da empresa | __________________ |
| SMTP: servidor, porta e usuário | SMTP autenticado com STARTTLS na porta 587 | __________________ |
| Remetente autorizado | treinamentos@suaempresa.com.br | __________________ |
| Destino de backup fora do servidor | Cofre corporativo/NAS/serviço de backup | __________________ |
| Iniciar vazio ou trazer dados existentes? | Decisão do proprietário da plataforma | __________________ |
| Janela de manutenção | Exemplo: diariamente às 02h00 | __________________ |
| Responsável por monitoramento | Nome e contato | __________________ |

Não preencha senhas neste documento. Elas devem ser entregues por um canal reservado.

Como ponto de partida de planejamento, reserve 2 a 4 CPUs virtuais, 8 GB de RAM e 80 GB de SSD, ajustando armazenamento ao volume de PDFs, vídeos e backups. Isso é uma estimativa inicial, **não uma capacidade validada de usuários simultâneos**. Faça um piloto com o volume real e acompanhe uso de memória, disco e tempo de resposta.

## 3. Preparar o acesso pela internet

Esta parte deve ser executada por quem administra a rede e o domínio da empresa. O instalador da aplicação pode acompanhar a lista, mas precisa das credenciais e atribuições correspondentes.

1. Reserve um IP interno fixo para o servidor. A TI pode fazer isso por reserva DHCP ou configuração do sistema.
2. Escolha um subdomínio, por exemplo `treinamentos.suaempresa.com.br`. Não use esse exemplo literalmente se a empresa não for dona do domínio.
3. No painel de DNS do domínio, crie um registro **A** para esse subdomínio apontando ao IP público de entrada da empresa.
4. Só publique um registro **AAAA** se a TI também tiver configurado e testado a entrada por IPv6. Um registro IPv6 incorreto pode impedir acessos e a emissão do certificado.
5. No firewall/roteador de borda, encaminhe TCP **80 e 443** ao IP interno do servidor. Se houver proxy corporativo, balanceador ou WAF, a TI deve adaptar o desenho; este roteiro pressupõe que o Caddy recebe HTTP/HTTPS diretamente.
6. Mantenha **5432 (PostgreSQL), 8000 (aplicação) e 2019 (administração local do Caddy)** sem encaminhamento público. Elas não são portas dos usuários.
7. Acesso administrativo por SSH/RDP deve seguir a VPN e as regras da empresa. Não é necessário abrir RDP/SSH publicamente para usar a plataforma.
8. Permita saída para DNS, atualização de pacotes, emissão/renovação de certificados HTTPS e SMTP. A emissão automática do certificado depende de o domínio chegar ao Caddy e de acesso de saída às autoridades certificadoras.
9. Se a internet da empresa estiver atrás de **CGNAT**, o simples encaminhamento de portas não será suficiente. A TI deve obter entrada pública com a operadora ou definir uma solução corporativa de publicação antes de continuar.
10. Na rede interna, pode ser necessário DNS interno apontando o mesmo nome ao IP interno, ou suporte a retorno NAT no roteador. Use o **mesmo nome HTTPS** dentro e fora da empresa.

Se 80/443 já atendem outro sistema, não desligue esse sistema. A TI precisa configurar um host separado no proxy existente ou uma VM/IP adequados.

## 4. Como ler e executar os manuais

- Execute os passos em ordem, no **servidor**, salvo indicação expressa de outra máquina.
- Um bloco com comandos é algo para copiar ao terminal; não copie os delimitadores de formatação.
- Execute um bloco por vez e confira o resultado antes do próximo. Se houver erro, pare naquele passo.
- `SUBSTITUA_...` marca um valor que precisa ser preenchido. Caminhos e nomes fixos do roteiro devem ser mantidos para que os blocos seguintes funcionem.
- Senhas digitadas no terminal podem não aparecer. Isso é normal.
- Um **serviço** é um programa que continua funcionando quando ninguém está conectado e volta após reiniciar o servidor.
- Um **ambiente virtual Python** separa as bibliotecas desta plataforma das usadas por outros programas.
- Uma **migração** cria ou atualiza as tabelas do banco. Não significa copiar automaticamente dados antigos.
- `127.0.0.1` significa “este próprio servidor”.

## 5. Dados existentes e comandos de demonstração

Os roteiros principais começam com **banco vazio**. Se houver cadastros e treinamentos que precisam ser preservados, leia [Transferência de dados existentes](05_TRANSFERIR_DADOS_EXISTENTES.md) antes de cadastrar qualquer informação no destino.

Não execute `criar_cursos_demonstracao` para preparar produção: esse comando contém exclusões de dados de negócio. Não execute `criar_dados_teste_slt` como parte da instalação; ele é uma carga de testes. Para começar vazio, bastam as migrações e a criação do administrador.

Os manuais não alteram as regras de acesso, permissões ou o código de negócio da plataforma. Há arquivos auxiliares de serviço e configuração que o instalador criará **no servidor** seguindo os exemplos.

## 6. Entrega e aceite

A instalação só deve ser considerada concluída depois de:

- Acesso HTTPS funcionando dentro da rede e em uma conexão externa, como celular com Wi-Fi desligado.
- Login administrativo e primeiro acesso de um técnico funcionando.
- PDF, vídeo e aparência da página funcionando.
- Curso de homologação concluído e certificado validado.
- E-mail de recuperação recebido e link funcionando.
- Reinício do servidor realizado em janela autorizada, com retorno automático do site.
- Backup gerado, copiado para fora do servidor e restaurado em banco separado de teste.
- Responsável definido para conferir backups, espaço livre, HTTPS e falhas de serviço.

Registre a data, versão entregue, nome do instalador, localização dos backups e contato de suporte. Os procedimentos foram conferidos por leitura do projeto e documentação dos fornecedores; **não foram executados em um servidor Windows/Ubuntu de produção nesta entrega**. O aceite acima é a validação obrigatória no ambiente real.

## 7. Fontes e manutenção do pacote

Compatibilidade Python/Django: [documentação do Django 6.0](https://docs.djangoproject.com/en/6.0/faq/install/). Publicação HTTPS: [Caddy — HTTPS automático](https://caddyserver.com/docs/automatic-https). As fontes específicas estão também em cada manual.

As versões e telas podem mudar depois desta edição. Preserve as versões principais indicadas; a TI deve escolher as atualizações corretivas disponíveis e homologá-las. Não troque a versão do Django do projeto como parte desta instalação sem uma entrega de software correspondente.
