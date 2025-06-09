
-- Extension DBlink
CREATE EXTENSION IF NOT EXISTS dblink;

CREATE TABLE IF NOT EXISTS dblink_config (
  nombre TEXT PRIMARY KEY,
  connstr TEXT NOT NULL
);

INSERT INTO dblink_config (nombre, connstr)
VALUES (
  'central',
  'host=192.168.1.13 port=5432 dbname=fonasa user=root password=toor'
)
ON CONFLICT (nombre) DO UPDATE
  SET connstr = EXCLUDED.connstr;

-- 1) Tabla Beneficiario
DROP TABLE IF EXISTS beneficiario CASCADE;
CREATE TABLE beneficiario (
    rut            VARCHAR(20)   PRIMARY KEY,
    nombre         VARCHAR(100)  NOT NULL,
    tramo_ingreso  CHAR(1)       NOT NULL,
    clave         VARCHAR(100)  NOT NULL
);

-- 2) Tabla Medico (sin columna id_region)
DROP TABLE IF EXISTS medico CASCADE;
CREATE TABLE medico (
    rut            VARCHAR(20)   PRIMARY KEY,
    nombre         VARCHAR(100)  NOT NULL,
    especialidad   VARCHAR(100)  NOT NULL,
    comuna   VARCHAR(100)  NOT NULL
);

-- 3) Tabla Bono (sin columna id_region)
DROP TABLE IF EXISTS bono CASCADE;
CREATE TABLE bono (
    id_bono          VARCHAR(20)   PRIMARY KEY,
    fecha_emision    DATE          NOT NULL,
    descripcion      TEXT          NULL,
    valor_total      DECIMAL(12,2) NOT NULL,
    valor_copago     DECIMAL(12,2) NOT NULL,
    valor_apagar     DECIMAL(12,2) NOT NULL,
    rut_beneficiario VARCHAR(20)   NOT NULL,
    rut_medico       VARCHAR(20)   NOT NULL,
    CONSTRAINT fk_bono_beneficiario
        FOREIGN KEY (rut_beneficiario)
        REFERENCES beneficiario(rut)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_bono_medico
        FOREIGN KEY (rut_medico)
        REFERENCES medico(rut)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

-- Triggers:
CREATE OR REPLACE FUNCTION replicar_medicos()
RETURNS TRIGGER AS $$
DECLARE
  conn_str TEXT;
  registros_central TEXT[];
  registro RECORD;
BEGIN
  -- Obtener string de conexión desde la tabla dblink_config
  SELECT connstr INTO conn_str FROM dblink_config WHERE nombre = 'central';

  -- Conectarse a la base central
  PERFORM dblink_connect('conn_central', conn_str);

  -- Obtener RUTs de médicos en la central
  SELECT array_agg(rut) INTO registros_central
  FROM dblink('conn_central', 'SELECT rut FROM medico') AS t(rut TEXT);

  -- Recorrer todos los médicos locales
  FOR registro IN SELECT * FROM medico LOOP
    IF registros_central IS NULL OR NOT registro.rut = ANY(registros_central) THEN
      BEGIN
        PERFORM dblink_exec('conn_central',
          'INSERT INTO medico (rut, nombre, especialidad, comuna) VALUES (' ||
          quote_literal(registro.rut) || ', ' ||
          quote_literal(registro.nombre) || ', ' ||
          quote_literal(registro.especialidad) || ', ' ||
          quote_literal(registro.comuna) || ')'
        );
      EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'No se pudo insertar medico % en central: %', registro.rut, SQLERRM;
      END;
    END IF;
  END LOOP;

  PERFORM dblink_disconnect('conn_central');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION replicar_bonos()
RETURNS TRIGGER AS $$
DECLARE
  conn_str TEXT;
  registros_central TEXT[];
  registro RECORD;
BEGIN
  -- Obtener string de conexión desde la tabla dblink_config
  SELECT connstr INTO conn_str FROM dblink_config WHERE nombre = 'central';

  -- Conectarse a la base central
  PERFORM dblink_connect('conn_central', conn_str);

  -- Obtener IDs de bonos en la central
  SELECT array_agg(id_bono) INTO registros_central
  FROM dblink('conn_central', 'SELECT id_bono FROM bono') AS t(id_bono TEXT);

  -- Recorrer todos los bonos locales
  FOR registro IN SELECT * FROM bono LOOP
    IF registros_central IS NULL OR NOT registro.id_bono = ANY(registros_central) THEN
      BEGIN
        PERFORM dblink_exec('conn_central',
          'INSERT INTO bono (id_bono, fecha_emision, descripcion, valor_total, valor_copago, valor_apagar, rut_beneficiario, rut_medico, id_region) VALUES (' ||
          quote_literal(registro.id_bono) || ', ' ||
          quote_literal(registro.fecha_emision) || ', ' ||
          COALESCE(quote_literal(registro.descripcion), 'NULL') || ', ' ||
          registro.valor_total || ', ' ||
          registro.valor_copago || ', ' ||
          registro.valor_apagar || ', ' ||
          quote_literal(registro.rut_beneficiario) || ', ' ||
          quote_literal(registro.rut_medico) || ', ' ||
          quote_literal(registro.id_region) || ')'
        );
      EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'No se pudo insertar bono % en central: %', registro.id_bono, SQLERRM;
      END;
    END IF;
  END LOOP;

  PERFORM dblink_disconnect('conn_central');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION replicar_beneficiarios()
RETURNS TRIGGER AS $$
DECLARE
  conn_str TEXT;
  registros_central TEXT[];
  registro RECORD;
BEGIN
  -- Obtener string de conexión desde dblink_config
  SELECT connstr INTO conn_str FROM dblink_config WHERE nombre = 'central';

  -- Conectar a la base de datos central
  PERFORM dblink_connect('conn_central', conn_str);

  -- Obtener RUTs de beneficiarios que ya existen en la central
  SELECT array_agg(rut) INTO registros_central
  FROM dblink('conn_central', 'SELECT rut FROM beneficiario') AS t(rut TEXT);

  -- Recorrer beneficiarios locales y replicar los que no estén
  FOR registro IN SELECT * FROM beneficiario LOOP
    IF registros_central IS NULL OR NOT registro.rut = ANY(registros_central) THEN
      BEGIN
        PERFORM dblink_exec('conn_central',
          'INSERT INTO beneficiario (rut, nombre, tramo_ingreso, clave) VALUES (' ||
          quote_literal(registro.rut) || ', ' ||
          quote_literal(registro.nombre) || ', ' ||
          quote_literal(registro.tramo_ingreso) || ', ' ||
          quote_literal(registro.clave) || ')'
        );
      EXCEPTION WHEN OTHERS THEN
        RAISE NOTICE 'No se pudo insertar beneficiario % en central: %', registro.rut, SQLERRM;
      END;
    END IF;
  END LOOP;

  PERFORM dblink_disconnect('conn_central');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;


CREATE TRIGGER trg_replicar_medico
AFTER INSERT ON medico
FOR EACH ROW
EXECUTE FUNCTION replicar_medicos();

CREATE TRIGGER trg_replicar_bono
AFTER INSERT ON bono
FOR EACH ROW
EXECUTE FUNCTION replicar_bonos();

CREATE TRIGGER trg_replicar_beneficiario
AFTER INSERT ON beneficiario
FOR EACH ROW
EXECUTE FUNCTION replicar_beneficiarios();


INSERT INTO beneficiario (rut, nombre, tramo_ingreso, clave)
VALUES
  ('12345678-9', 'Pelao Rojas', 'A', '1234')
ON CONFLICT (rut) DO NOTHING;

INSERT INTO medico (rut, nombre, especialidad, comuna)
VALUES
  ('33333333-3', 'Dra. Pelada', 'Dermatologia', 'La Serena')
ON CONFLICT (rut) DO NOTHING;
