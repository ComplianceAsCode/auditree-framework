.. -*- mode:rst; coding:utf-8 -*-

.. _verifying-signed-evidence:

Verifying Signed Evidence
=========================

Follow the instructions to manually verify the sample evidence below::

  -----BEGIN AGENT-----
  auditree.local
  -----END AGENT-----
  -----BEGIN CONTENT-----
  This is my evidence.
  -----END CONTENT-----
  -----BEGIN DIGEST-----
  81ddd37cb8aba90077a717b7d6c067815add58e658bb2be0dea4d4d9301c762d
  -----END DIGEST-----
  -----BEGIN SIGNATURE-----
  xRIu2dey1WSCSRpBWHlar5XUv13vZtm1n/KEDckA85UoQjEqEo7xlmnpzBtkNcieME6frhBMmBOYPW4uFYS1EUtLxkixYkYjt3wKlHl8CkvKDFoqAMqG8AC/cCdqwP7D7SlO5RH1pJ1kp2yX2XB2MTMHkd/9tguNZBpaCnscYCmpBvng6okB7HbToOlVUfKY1tWDDIm3JefFMEoJqXgIEZMmVnF+nLniF/PvPTL+q38e6Wd1xeJpZYiLk12imarzkf9MweA5D22xkv51pI2ils3jovxymzio26cSkL7iHBsbiNOWWXoETo0aYm2g9CzhxnRGku9OEkW97JGNASkjSw==
  -----END SIGNATURE-----

1. Fetch the public key for the ``auditree.local`` agent. This can be collected
   directly from the agent or the public keys evidence (available in the locker
   under ``raw/auditree/agent_public_keys.json``)::

     $ cat > key.pub
     -----BEGIN PUBLIC KEY-----
     MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxYosRYnahnSuH3SmNupn
     zQhxJsDEhqChKjrcyN19L8+vcjUUiMSaKRoAHuUKp5Pfwkoylryd4AyXIU9UnXZg
     dIOl2+r5xzXqfdLwi+PAU/eEWPLAQfCpIodqKqBLCyzpMoJHv9GDqg8XJkY/2i8j
     7oiqLR7vibIgRAJXqF95KdNvbW7Gvu8JHigN4aoGdbQSPp/jJ30wBvy7hHOSrMWF
     iQUt7H25YbvOZGWQeC8HZ2EXruzG+FV2rkW52FaTn31lX1EEc2Yz8AI7/yF/8C5j
     SSL/pmzxBzh/P4zGDNlm2habpwAIQpHnJJ8XeXYS//RXuOYNObeRwfhm82TB9+nS
     lQIDAQAB
     -----END PUBLIC KEY-----

2. Save the evidence content to your local filesystem and verify the digest::

     $ cat > evidence.txt
     This is my evidence.

     $ openssl dgst -sha256 evidence.txt
     SHA256(evidence.txt)= 81ddd37cb8aba90077a717b7d6c067815add58e658bb2be0dea4d4d9301c762d

   *Be sure not to add any additional whitespace when saving evidence locally.*

3. Save the signature to your local filesystem::

     $ cat > signature.txt
     xRIu2dey1WSCSRpBWHlar5XUv13vZtm1n/KEDckA85UoQjEqEo7xlmnpzBtkNcieME6frhBMmBOYPW4uFYS1EUtLxkixYkYjt3wKlHl8CkvKDFoqAMqG8AC/cCdqwP7D7SlO5RH1pJ1kp2yX2XB2MTMHkd/9tguNZBpaCnscYCmpBvng6okB7HbToOlVUfKY1tWDDIm3JefFMEoJqXgIEZMmVnF+nLniF/PvPTL+q38e6Wd1xeJpZYiLk12imarzkf9MweA5D22xkv51pI2ils3jovxymzio26cSkL7iHBsbiNOWWXoETo0aYm2g9CzhxnRGku9OEkW97JGNASkjSw==

4. Convert the Base64 signature to binary::

     $ openssl base64 -d -in signature.txt -out evidence.sig

5. Verify the signature::

     $ openssl dgst -sha256 -verify key.pub -signature evidence.sig -sigopt rsa_padding_mode:pss evidence.txt
     Verified OK

   If the verification is successful, the OpenSSL command will print the
   ``Verified OK`` message, otherwise it will print ``Verification Failure``.
